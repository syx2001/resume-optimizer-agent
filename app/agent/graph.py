from langgraph.graph import StateGraph, START, END
from app.agent.state import AgentState, AgentContext
from app.agent.node import (
    intake_node,
    load_user_resume_node,
    parse_resume_node,
    save_resume_node,
    parse_job_node,
    retrieve_guidelines_node,
    match_node,
    plan_node,
    plan_approval_node,
    repair_node,
    rewrite_node,
    validate_node,
    blocked_node,
    finalize_node,
)
from app.agent.routing import (
    route_after_intake,
    route_after_load_resume,
    route_after_parse_resume,
    route_after_parse_job,
    route_after_match,
    route_after_plan,
    route_after_plan_approval,
    route_after_rewrite,
    route_after_validation,
    route_after_repair,
    route_after_blocked,
)

def build_graph():
    #初始化
    builder = StateGraph(AgentState, context_schema=AgentContext)
    #增加node
    builder.add_node("intake",intake_node)
    builder.add_node("load_resume",load_user_resume_node)
    builder.add_node("parse_resume",parse_resume_node)
    builder.add_node("save_resume",save_resume_node)
    builder.add_node("parse_job",parse_job_node)
    builder.add_node("retrieve_guidelines",retrieve_guidelines_node)
    builder.add_node("match",match_node)
    builder.add_node("plan",plan_node)
    builder.add_node("plan_approval",plan_approval_node)
    builder.add_node("repair",repair_node)
    builder.add_node("rewrite",rewrite_node)
    builder.add_node("validate",validate_node)
    builder.add_node("blocked",blocked_node)
    builder.add_node("finalize",finalize_node)
    #连接edge
    builder.add_edge(START,"intake")
    builder.add_conditional_edges("intake",route_after_intake,
                    {
                        "load_resume":"load_resume",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("load_resume", route_after_load_resume,
                    {
                        "parse_resume": "parse_resume",
                        "parse_job": "parse_job",
                        "finalize": "finalize",
                    })
    builder.add_conditional_edges("parse_resume",route_after_parse_resume,
                    {
                        "save_resume":"save_resume",
                        "finalize":"finalize"
                    })
    builder.add_edge("save_resume","parse_job")
    builder.add_conditional_edges("parse_job",route_after_parse_job,
                    {
                        "retrieve_guidelines":"retrieve_guidelines",
                        "finalize":"finalize"
                    })
    builder.add_edge("retrieve_guidelines", "match")
    builder.add_conditional_edges("match",route_after_match,
                    {
                        "plan":"plan",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("plan",route_after_plan,
                    {
                        "plan_approval":"plan_approval",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("plan_approval",route_after_plan_approval,
                    {
                        "blocked":"blocked",
                        "rewrite":"rewrite",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("rewrite",route_after_rewrite,
                    {
                        "validate":"validate",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("validate",route_after_validation,
                    {
                        "repair": "repair",
                        "blocked": "blocked",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("repair",route_after_repair,
                    {
                        "rewrite": "rewrite",
                        "finalize":"finalize"
                    })
    builder.add_conditional_edges("blocked",route_after_blocked,
                    {
                        "finalize":"finalize"
                    })
    builder.add_edge("finalize",END)

    return builder

def compile_graph(*, checkpointer=None, store=None):
    builder = build_graph()

    return builder.compile(
        checkpointer=checkpointer,
        store=store,
    )
