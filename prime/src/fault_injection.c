#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <time.h>
#include "spu_alarm.h"
#include "fault_injection.h"
#include "signature.h"
#include "data_structs.h"

extern server_data_struct DATA;
extern server_variables   VAR;
extern network_variables  NET;
extern benchmark_struct   BENCH;
extern int Use_FI;

const char* packet_type_names[] = {"DUMMY", 
		   "PO_REQUEST", "PO_ACK", "PO_ARU", "PROOF_MATRIX",
		   "PRE_PREPARE", "PREPARE", "COMMIT", "RECON",
           "TAT_MEASURE", "RTT_PING", "RTT_PONG", "RTT_MEASURE", "TAT_UB",
           "NEW_LEADER", "NEW_LEADER_PROOF",
           "RB_INIT", "RB_ECHO", "RB_READY",
           "REPORT", "PC_SET", "VC_LIST", "VC_PARTIAL_SIG", "VC_PROOF",
           "REPLAY", "REPLAY_PREPARE", "REPLAY_COMMIT",
           "ORD_CERT", "PO_CERT", "CATCHUP_REQUEST", "JUMP",
           "NEW_INCARNATION", "INCARNATION_ACK", "INCARNATION_CERT",
           "PENDING_STATE", "PENDING_SHARE",
           "RESET_VOTE", "RESET_SHARE",
           "RESET_PROPOSAL", "RESET_PREPARE", "RESET_COMMIT",
           "RESET_NEWLEADER", "RESET_NEWLEADERPROOF", 
           "RESET_VIEWCHANGE", "RESET_NEWVIEW", "RESET_CERT",
		   "UPDATE", "CLIENT_RESPONSE", 
           "OOB_CONFIG", "IB_CONFIG,MAX_MESS_TYPE"};

/* Move Aren's test cases to one place in prime for ease of use.
* Just run a switch statement across all the relevant packet types,
* letting us add more later more conveniently. */
signed_message *FAULT_INJECTION_Manipulate_Message (signed_message *message)
{
    //printf("Current FI Value at Signature %d\n", Use_FI);
    if(Use_FI == 1)
    {
        switch ((enum packet_types) message->type)
        {
            case PO_ACK:
            //Aren Test 1
            po_ack_message *po_ack_specific = (po_ack_message*)(message + 1);
            po_ack_part *ack_part = (po_ack_part *)(po_ack_specific + 1);
            for(int i = 0; i < po_ack_specific->num_ack_parts; i++)
            {
                if (VAR.My_Server_ID == 1 && ack_part->seq.seq_num % 10 == 0) {
                    //printf("\nNo Change in the seq\n");
                    srand(time(NULL)); 
                    ack_part->seq.seq_num = rand();//%51;
                    ack_part->seq.incarnation = rand();
                    ack_part = (po_ack_part *)(ack_part + 1);
                }
            }
            // small change ToDo change -->> ps.seq_num--; ps.seq_num;
            //random change in sequence number    ps.seq_num = rand();
            break;

            case PRE_PREPARE:
            pre_prepare_message *pp_specific = (pre_prepare_message *)(message + 1);
            if (VAR.My_Server_ID == 1 && pp_specific->seq_num % 10 == 0 ){
                srand(time(NULL)); 
                pp_specific->seq_num = rand();// % 51; 
            }
            break;
            
            default:
            break;
        }
    }
    else if(Use_FI == 2)
    {
        srand(time(NULL));
        unsigned int offset = rand() % message->len;
        char rand_val = rand() % 256;
        char *offset_pointer = ((char *) message) + offset;

        char base_val = *offset_pointer;
        *offset_pointer = rand_val;

        /* Not really sure how to log these changes uniquely here,
         * using type + len for now, but not if sure that 
         * guarantees a unique marker for each packet. */
        Alarm(PRINT, "Type: %s - Len: %d - Modified Byte: %d from %d to %d.\n", 
                packet_type_names[message->type], message->len, offset, base_val, rand_val);
    }

    return message;
}