from app.agent.state import AgentState
from app.schemas import ValidationResult
MAX_REPAIR_ATTEMPTS = 1
def route_after_intake(state: AgentState) -> str:
    """
    intake 节点执行后的路由。

    成功：
        load_resume

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "load_resume"


def route_after_load_resume(state: AgentState) -> str:
    """Stop cleanly when no request or saved default resume is available."""
    if state.get("task_status") == "failed":
        return "finalize"
    if (
        state.get("resume_source") == "saved_default"
        and state.get("resume_profile")
    ):
        return "parse_job"
    return "parse_resume"


def route_after_parse_resume(state: AgentState) -> str:
    """
    简历解析节点执行后的路由。

    成功：
        save_resume

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "save_resume"


def route_after_parse_job(state: AgentState) -> str:
    """
    JD 解析节点执行后的路由。

    成功：
        match

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "retrieve_guidelines"


def route_after_match(state: AgentState) -> str:
    """
    岗位匹配分析后的路由。

    成功：
        plan

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "plan"


def route_after_plan(state: AgentState) -> str:
    """
    优化计划生成后的路由。

    成功：
        plan_approval

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "plan_approval"


def route_after_plan_approval(state: AgentState) -> str:
    """
    用户审批优化计划后的路由。

    用户批准：
        rewrite

    用户拒绝：
        blocked
    """

    if state.get("task_status") == "failed":
        return "finalize"

    if state.get("plan_approved") is True:
        return "rewrite"

    return "blocked"


def route_after_rewrite(state: AgentState) -> str:
    """
    简历改写后的路由。

    成功：
        validate

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "validate"


def route_after_validation(state: AgentState) -> str:
    """
    根据候选简历校验结果决定下一步。

    路由规则：

    1. validate 本身执行异常
       -> finalize

    2. 没有任何校验结果
       -> blocked

    3. 所有校验都通过
       -> finalize

    4. 存在不可自动修复的问题
       -> blocked

    5. 可以修复，但已经达到最大修复次数
       -> blocked

    6. 所有失败项均可自动修复，且未达到修复次数上限
       -> repair
    """

    # validate 节点本身发生执行异常。
    if state.get("task_status") == "failed":
        return "finalize"

    raw_results = state.get("validation_results", [])

    # 没有产生任何校验结果时，
    # 不能直接认为校验通过。
    if not raw_results:
        return "blocked"

    validation_results = [
        ValidationResult.model_validate(item)
        for item in raw_results
    ]

    failed_results = [
        result
        for result in validation_results
        if not result.passed
    ]

    # 所有检查都通过。
    if not failed_results:
        return "finalize"

    # 只要存在一个不可自动修复的问题，
    # 就停止自动修复。
    if any(
        not result.repairable
        for result in failed_results
    ):
        return "blocked"

    repair_attempts = state.get(
        "repair_attempts",
        0,
    )

    # 达到最大修复次数，停止循环。
    if repair_attempts >= MAX_REPAIR_ATTEMPTS:
        return "blocked"

    # 当前所有失败项都可以自动修复。
    return "repair"


def route_after_repair(state: AgentState) -> str:
    """
    repair 节点执行后的路由。

    成功：
        rewrite

    失败：
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "rewrite"


def route_after_blocked(state: AgentState) -> str:
    """
    blocked 节点执行后统一进入 finalize。

    blocked 是正常的业务停止状态，
    最终仍然需要构造 ResumeOptimizationResult。
    """

    return "finalize"
