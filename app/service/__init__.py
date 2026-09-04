"""简历优化领域服务的统一导出入口。"""

from app.service.job_parser import JobParser
from app.service.matcher import ResumeJobMatcher
from app.service.optimizer import ResumeOptimizer
from app.service.repair import ResumeRepairService
from app.service.resume_parser import ResumeParser
from app.service.validator import ResumeValidator

__all__ = [
    "ResumeParser",  # 简历解析
    "JobParser",  # JD 解析
    "ResumeJobMatcher",  # 简历与岗位匹配
    "ResumeOptimizer",  # 计划生成和简历改写
    "ResumeValidator",  # 优化结果校验
    "ResumeRepairService",  # 根据校验结果生成修复指令
]
