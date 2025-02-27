#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <time.h>
#include "fault_injection.h"
#include "signature.h"
#include "data_structs.h"

extern server_data_struct DATA;
extern server_variables   VAR;
extern network_variables  NET;
extern benchmark_struct   BENCH;
extern int Use_FI;

/* Move Aren's test cases to one place in prime for ease of use.
* Just run a switch statement across all the relevant packet types,
* letting us add more later more conveniently. */
signed_message *FAULT_INJECTION_Manipulate_Message (signed_message *message)
{
    //printf("Current FI Value at Signature %d\n", Use_FI);
    if(Use_FI > 0)
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

    return message;
}