export const roles = { analyst: '分析员', reviewer: '复核员', viewer: '观察员' };
export const stages = {
  queued: '排队中',
  running: '计算中',
  succeeded: '已完成',
  failed: '失败',
  held: '暂缓排队',
  pending: '复检线待算',
  ready: '复检线就绪',
  superseded: '旧线已切换',
};
export const decisions = { approve: '签发', hold: '暂缓' };
export const auditActions = {
  dataset_imported: '导入数据',
  dataset_corrected: '按编号更正',
  run_queued: '提交计算',
  run_succeeded: '完成计算',
  run_failed: '计算失败',
  run_held: '暂缓排队',
  run_requeued: '恢复排队',
  calibration_queued: '复检线重算',
  calibration_activated: '切换复检线',
  calibration_untrusted: '复检线可信度不足',
  calibration_failed: '复检线失败',
  review_approve: '签发交接',
  review_hold: '暂缓交接',
};
