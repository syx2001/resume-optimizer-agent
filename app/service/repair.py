"""简历修复指令生成服务。"""

from app.schemas import ValidationResult


class ResumeRepairService:
    """
    根据 ValidationResult 生成下一轮简历改写需要遵守的修复指令。

    本 Service 不负责：
    1. 调用 LLM；
    2. 修改简历；
    3. LangGraph Workflow 路由；
    4. 判断是否应该继续修复。

    是否进入 repair 由 Graph Router 决定。
    """

    def build_instructions(
        self,
        optimized_resume: str,
        validation_results: list[ValidationResult],
    ) -> list[str]:
        """
        将可自动修复的校验失败项转换为 repair_instructions。

        Args:
            optimized_resume:
                当前候选简历。
                第一版主要用于基本输入检查，
                后续如果需要可以用于更复杂的定位逻辑。

            validation_results:
                当前校验阶段产生的结果。

        Returns:
            list[str]:
                下一轮 rewrite 使用的修复指令。

        Raises:
            ValueError:
                当前候选简历为空，
                或不存在可自动修复的问题时抛出。
        """

        if not optimized_resume.strip():
            raise ValueError("当前候选简历不能为空。")

        instructions: list[str] = []

        for result in validation_results:

            # 已通过的检查不需要修复
            if result.passed:
                continue

            # 不可自动修复的问题不能生成自动修复指令
            if not result.repairable:
                continue

            if result.suggestion:
                instruction = (
                    f"[{result.category}] "
                    f"{result.suggestion.strip()}"
                )
            else:
                instruction = (
                    f"[{result.category}] "
                    f"请修复以下问题：{result.message.strip()}"
                )

            instructions.append(instruction)

        if not instructions:
            raise ValueError(
                "当前没有可以自动修复的校验问题。"
            )

        return instructions