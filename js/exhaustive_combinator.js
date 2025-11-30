import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * ComfyUI 穷举组合节点 - 前端交互模块
 */

app.registerExtension({
  name: "SuperSuger.ExhaustiveCombinator",

  async setup() {
    console.log("[ExhaustiveCombinator] 扩展已加载");

    /**
     * 监听后端信号: exhaustive-add-queue
     * 收到信号后自动触发下一次队列执行
     */
    api.addEventListener("exhaustive-add-queue", (event) => {
      const data = event.detail || {};
      const nodeId = data.node_id;

      console.log("[DEBUG-JS] ========== 收到后端自动队列信号 ==========");
      console.log("  - 节点 ID:", nodeId);

      if (!app.queuePrompt) {
        console.error("[ERROR-JS] 无法找到 app.queuePrompt 函数。");
        return;
      }

      // 使用 setTimeout 缓冲,确保在当前执行流程结束后再触发下一轮
      setTimeout(() => {
        try {
          console.log("[DEBUG-JS] 准备触发 app.queuePrompt (延时 100ms)...");

          // 关键触发点：调用队列 API
          const result = app.queuePrompt(0, 1);

          if (result && result.promise) {
            console.log(
              "[SUCCESS-JS] app.queuePrompt 成功调用，新任务已提交到队列。"
            );
          } else {
            console.warn(
              "[WARN-JS] app.queuePrompt 调用可能失败或返回非预期结果。"
            );
          }
        } catch (queueError) {
          console.error("[ERROR-JS] 自动排队捕获到异常:", queueError);
        }
      }, 100);
    });

    /**
     * 监听后端信号: exhaustive-node-feedback
     * 用于更新节点 Widget 进度信息
     */
    api.addEventListener("exhaustive-node-feedback", (event) => {
      const data = event.detail || {};
      const nodeId = data.node_id;

      try {
        console.log(
          `[DEBUG-JS] 收到进度更新信号: Node ${nodeId} -> ${data.widget_name} = ${data.value}`
        );
      } catch (error) {
        console.error("[ERROR-JS] 进度更新失败:", error);
      }
    });
  },

  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    if (nodeData.name === "ExhaustivePromptCombinator") {
      console.log("[ExhaustiveCombinator] 节点注册成功，等待创建实例...");
    }
  },
});
