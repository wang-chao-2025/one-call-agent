"""
AIOps task templates.
"""

from textwrap import dedent


def build_aiops_task() -> str:
    """Return the default AIOps diagnosis task prompt."""
    return dedent(
        """
        诊断当前系统是否存在告警，如存在请详细分析告警原因并生成诊断报告。

        诊断报告输出格式要求：
        ```markdown
        # 告警分析报告

        ## 活跃告警清单
        - 列出当前活跃告警、级别、受影响服务、首次触发时间和最新触发时间

        ## 告警根因分析
        - 说明告警详情
        - 结合监控症状描述当前状态
        - 引用工具查询到的关键日志和指标证据
        - 给出根因结论

        ## 处理方案
        - 列出已经执行过的排查步骤
        - 给出明确的处理建议
        - 说明预期效果

        ## 结论
        - 总结整体情况
        - 提炼关键发现
        - 给出后续建议和风险评估
        ```

        重要要求：
        - 最终输出必须是纯 Markdown 文本，不要输出 JSON
        - 所有内容必须基于工具查询的真实结果，严禁编造
        - 如果某一步骤失败，必须在结论中明确说明，不要跳过
        """
    ).strip()
