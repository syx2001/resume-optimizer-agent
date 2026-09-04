from app.agent.state import AgentState
from app.schemas import ValidationResult
MAX_REPAIR_ATTEMPTS = 1
def route_after_intake(state: AgentState) -> str:
    """
    intake 鑺傜偣鎵ц鍚庣殑璺敱銆?

    鎴愬姛锛?
        load_resume

    澶辫触锛?
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
    绠€鍘嗚В鏋愯妭鐐规墽琛屽悗鐨勮矾鐢便€?

    鎴愬姛锛?
        save_resume

    澶辫触锛?
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "save_resume"


def route_after_parse_job(state: AgentState) -> str:
    """
    JD 瑙ｆ瀽鑺傜偣鎵ц鍚庣殑璺敱銆?

    鎴愬姛锛?
        match

    澶辫触锛?
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "retrieve_guidelines"


def route_after_match(state: AgentState) -> str:
    """
    宀椾綅鍖归厤鍒嗘瀽鍚庣殑璺敱銆?

    鎴愬姛锛?
        plan

    澶辫触锛?
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "plan"


def route_after_plan(state: AgentState) -> str:
    """
    浼樺寲璁″垝鐢熸垚鍚庣殑璺敱銆?

    鎴愬姛锛?
        plan_approval

    澶辫触锛?
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "plan_approval"


def route_after_plan_approval(state: AgentState) -> str:
    """
    鐢ㄦ埛瀹℃壒浼樺寲璁″垝鍚庣殑璺敱銆?

    鐢ㄦ埛鎵瑰噯锛?
        rewrite

    鐢ㄦ埛鎷掔粷锛?
        blocked
    """

    if state.get("task_status") == "failed":
        return "finalize"

    if state.get("plan_approved") is True:
        return "rewrite"

    return "blocked"


def route_after_rewrite(state: AgentState) -> str:
    """
    绠€鍘嗘敼鍐欏悗鐨勮矾鐢便€?

    鎴愬姛锛?
        validate

    澶辫触锛?
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "validate"


def route_after_validation(state: AgentState) -> str:
    """
    鏍规嵁鍊欓€夌畝鍘嗘牎楠岀粨鏋滃喅瀹氫笅涓€姝ャ€?

    璺敱瑙勫垯锛?

    1. validate 鏈韩鎵ц寮傚父
       -> finalize

    2. 娌℃湁浠讳綍鏍￠獙缁撴灉
       -> blocked

    3. 鎵€鏈夋牎楠岄兘閫氳繃
       -> finalize

    4. 瀛樺湪涓嶅彲鑷姩淇鐨勯棶棰?
       -> blocked

    5. 鍙慨澶嶏紝浣嗗凡缁忚揪鍒版渶澶т慨澶嶆鏁?
       -> blocked

    6. 鎵€鏈夊け璐ラ」鍧囧彲鑷姩淇锛屽苟涓旀湭杈惧埌淇娆℃暟涓婇檺
       -> repair
    """

    # validate 鑺傜偣鏈韩鍙戠敓鎵ц寮傚父銆?
    if state.get("task_status") == "failed":
        return "finalize"

    raw_results = state.get("validation_results", [])

    # 娌℃湁浜х敓浠讳綍鏍￠獙缁撴灉鏃讹紝
    # 涓嶈兘鐩存帴璁や负鏍￠獙閫氳繃銆?
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

    # 鎵€鏈夋鏌ラ兘閫氳繃銆?
    if not failed_results:
        return "finalize"

    # 鍙瀛樺湪涓€涓笉鍙嚜鍔ㄤ慨澶嶇殑闂锛?
    # 灏卞仠姝㈣嚜鍔ㄤ慨澶嶃€?
    if any(
        not result.repairable
        for result in failed_results
    ):
        return "blocked"

    repair_attempts = state.get(
        "repair_attempts",
        0,
    )

    # 杈惧埌鏈€澶т慨澶嶆鏁帮紝鍋滄寰幆銆?
    if repair_attempts >= MAX_REPAIR_ATTEMPTS:
        return "blocked"

    # 褰撳墠鎵€鏈夊け璐ラ」閮藉彲浠ヨ嚜鍔ㄤ慨澶嶃€?
    return "repair"


def route_after_repair(state: AgentState) -> str:
    """
    repair 鑺傜偣鎵ц鍚庣殑璺敱銆?

    鎴愬姛锛?
        rewrite

    澶辫触锛?
        finalize
    """

    if state.get("task_status") == "failed":
        return "finalize"

    return "rewrite"


def route_after_blocked(state: AgentState) -> str:
    """
    blocked 鑺傜偣鎵ц鍚庣粺涓€杩涘叆 finalize銆?

    blocked 鏄甯镐笟鍔″仠姝㈢姸鎬侊紝
    鏈€缁堜粛鐒堕渶瑕佹瀯閫?ResumeOptimizationResult銆?
    """

    return "finalize"
