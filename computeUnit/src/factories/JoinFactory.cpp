#include <factories/JoinFactory.hpp>

#include <operators/HashJoinOperator.hpp>
#include <operators/HashJoinOperatorMat.hpp>
#include <operators/MergeJoinOperator.hpp>
#include <operators/NestedLoopJoinOperator.hpp>

JoinFactory::JoinFactory() : AbstractOperatorFactory() {
}

AbstractOperator* JoinFactory::create_operator(WorkItem& witem) {
    AbstractOperator* op = nullptr;
    switch( witem.operatorid() ) {
        case OperatorType::OP_MERGEJOIN: {
            LOG_ERROR("[JoinFactory] Error. MergeJoin is not yet implemented." << std::endl;)
            exit(-11);
            // op = new MergeJoinOperator(request);
        }break;
        case OperatorType::OP_NLJ: {
            LOG_ERROR("[JoinFactory] Error. NestedLoopJoin is not yet implemented." << std::endl;)
            exit(-11);
            // op = new NestedLoopJoinOperator(request);
        }break;
        case OperatorType::OP_HASHJOIN: {
            op = new HashJoinOperator(witem);
        }break;
        case OperatorType::OP_HASHJOIN_MAT: {
            op = new HashJoinOperatorMat(witem);
        }break;
        default: {
            LOG_ERROR("[JoinFactory] Error. Requesting unknown Operator type: " << OperatorType_Name(witem.operatorid()) << std::endl;)
            exit(-11);
        }
    }
    return op;
}
