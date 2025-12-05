/**
 * ComfyUI 前端扩展：动态提示词池输入槽
 *
 * 功能：
 * - 监听节点连接事件
 * - 动态添加/移除提示词池输入槽
 * - 连接 pool_N 后自动添加 pool_N+1
 * - 断开连接后自动移除后续空闲的输入槽
 *
 * 文件位置：
 * custom_nodes/your_node/js/dynamic_pools.js
 */

import { app } from "../../../scripts/app.js";

// 节点类名（必须与 __init__.py 中注册的节点名匹配）
const TARGET_NODE_TYPE = "SG_ExhaustiveCombinator";

// 最大支持的池数量
const MAX_POOLS = 15;

/**
 * 检查输入槽是否已连接
 */
function isInputConnected(node, inputName) {
  if (!node.inputs) return false;

  const input = node.inputs.find((i) => i.name === inputName);
  if (!input) return false;

  return input.link != null;
}

/**
 * 获取当前已连接的最大池编号
 */
function getMaxConnectedPool(node) {
  let maxPool = 0;

  for (let i = 1; i <= MAX_POOLS; i++) {
    const inputName = `pool_${i}`;
    if (isInputConnected(node, inputName)) {
      maxPool = i;
    }
  }

  return maxPool;
}

/**
 * 获取节点的原始输入定义（从 Python 端）
 */
function getOriginalInputs(node) {
  // 保存在节点上，避免重复获取
  if (node._originalPoolInputs) {
    return node._originalPoolInputs;
  }

  const poolInputs = [];

  // 从当前输入中提取所有 pool 定义
  if (node.inputs) {
    for (let i = 1; i <= MAX_POOLS; i++) {
      const inputName = `pool_${i}`;
      const input = node.inputs.find((inp) => inp.name === inputName);
      if (input) {
        // 保存输入的完整定义
        poolInputs.push({
          name: input.name,
          type: input.type,
          link: input.link,
          slot_index: input.slot_index,
        });
      }
    }
  }

  node._originalPoolInputs = poolInputs;
  return poolInputs;
}

/**
 * 重建节点的输入槽列表
 */
function rebuildInputs(node) {
  const maxConnected = getMaxConnectedPool(node);
  const maxVisible =
    maxConnected === 0 ? 1 : Math.min(maxConnected + 1, MAX_POOLS);

  console.log(
    `[DynamicPools] Rebuilding inputs for node ${node.id}: maxConnected=${maxConnected}, maxVisible=${maxVisible}`
  );

  // 获取原始输入定义
  const originalPoolInputs = getOriginalInputs(node);

  if (originalPoolInputs.length === 0) {
    console.log(`[DynamicPools] No pool inputs found for node ${node.id}`);
    return;
  }

  // 保存非 pool 的输入（如 template_text）
  const nonPoolInputs = node.inputs.filter(
    (inp) => !inp.name.startsWith("pool_")
  );

  // 保存当前的连接状态
  const connections = {};
  for (let i = 1; i <= MAX_POOLS; i++) {
    const inputName = `pool_${i}`;
    const input = node.inputs.find((inp) => inp.name === inputName);
    if (input && input.link != null) {
      connections[inputName] = input.link;
    }
  }

  // 清空并重建输入数组
  node.inputs = [...nonPoolInputs];

  // 只添加应该可见的 pool 输入
  for (let i = 1; i <= maxVisible; i++) {
    const originalInput = originalPoolInputs[i - 1];
    if (originalInput) {
      const newInput = {
        name: originalInput.name,
        type: originalInput.type,
        link: connections[originalInput.name] || null,
        slot_index: node.inputs.length,
      };

      node.inputs.push(newInput);
    }
  }

  console.log(
    `[DynamicPools] Node ${node.id} now has ${node.inputs.length} inputs (${
      node.inputs.filter((i) => i.name.startsWith("pool_")).length
    } pools visible)`
  );

  // 调整节点大小
  if (node.setSize) {
    node.setSize(node.computeSize());
  }

  // 刷新画布
  if (node.setDirtyCanvas) {
    node.setDirtyCanvas(true, true);
  }

  if (node.graph) {
    node.graph.setDirtyCanvas(true, true);
  }
}

/**
 * 节点加载后的初始化
 */
function setupNode(node) {
  console.log(`[DynamicPools] Setting up node ${node.id} (${node.type})`);

  // 延迟初始化，确保所有输入槽已完全创建
  setTimeout(() => {
    console.log(`[DynamicPools] Initializing node ${node.id}`);
    rebuildInputs(node);
  }, 100);

  // 保存原始的 onConnectionsChange 方法
  const originalOnConnectionsChange = node.onConnectionsChange;

  // 重写 onConnectionsChange 方法以监听连接变化
  node.onConnectionsChange = function (type, index, connected, link_info) {
    // 调用原始方法
    if (originalOnConnectionsChange) {
      originalOnConnectionsChange.apply(this, arguments);
    }

    // 只处理输入连接变化
    if (type === LiteGraph.INPUT || type === 1) {
      console.log(
        `[DynamicPools] Connection change on node ${this.id}: index=${index}, connected=${connected}`
      );

      // 延迟更新，确保连接状态已完全更新
      setTimeout(() => {
        rebuildInputs(this);
      }, 50);
    }
  };

  // 监听节点配置变化（用于处理工作流加载等情况）
  const originalConfigure = node.configure;
  node.configure = function (info) {
    if (originalConfigure) {
      originalConfigure.apply(this, arguments);
    }

    console.log(`[DynamicPools] Node ${this.id} configured`);

    // 延迟更新
    setTimeout(() => {
      rebuildInputs(this);
    }, 100);
  };
}

/**
 * 注册扩展
 */
app.registerExtension({
  name: "SG.DynamicPromptPools",

  async beforeRegisterNodeDef(nodeType, nodeData, app) {
    // 只处理目标节点类型
    if (nodeData.name !== TARGET_NODE_TYPE) {
      return;
    }

    console.log(`[DynamicPools] Registering extension for ${TARGET_NODE_TYPE}`);

    // 保存原始的 onNodeCreated 方法
    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;

    // 重写 onNodeCreated 方法
    nodeType.prototype.onNodeCreated = function () {
      // 调用原始方法
      if (originalOnNodeCreated) {
        originalOnNodeCreated.apply(this, arguments);
      }

      // 设置动态输入功能
      setupNode(this);
    };
  },

  async loadedGraphNode(node, app) {
    // 当从工作流加载节点时也需要设置
    if (node.type === TARGET_NODE_TYPE) {
      console.log(`[DynamicPools] Loaded graph node ${node.id}`);
      setupNode(node);
    }
  },
});
