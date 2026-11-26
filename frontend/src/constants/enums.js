export const roles = { analyst: '分析员', reviewer: '复核员', viewer: '观察员' };
export const stages = { queued: '排队中', running: '计算中', succeeded: '已完成', failed: '失败' };
export const decisions = { approve: '签发', hold: '暂缓' };
export const auditActions = {
  dataset_imported: '导入数据',
  run_queued: '提交计算',
  run_succeeded: '完成计算',
  run_failed: '计算失败',
  review_approve: '签发交接',
  review_hold: '暂缓交接',
};
