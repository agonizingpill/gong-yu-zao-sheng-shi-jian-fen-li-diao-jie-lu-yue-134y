# 001 初始领域结构

由 `src/models.py` SQLAlchemy metadata 建立17张领域/支撑表，首次启动执行create_all。投诉是所有同卷写入的锁根；协议动作先锁投诉再读取协议。MySQL显式READ COMMITTED，防止锁等待后读取旧聚合快照。事件同卷/同地点/同时间唯一；签字同协议/同人唯一；复验事件和复发事件一对一约束。

## 设备能量归因（equipment / calibrations / energy_ledgers / energy_lines）

- `equipment`：卷宗内设备名称唯一；`calibrations` 标记单台设备启停采样，一条采样只能标定一台设备（`event_id` 唯一），混合采样不能作为模板。
- `energy_ledgers.client_token` 全局唯一，是重试幂等键；同一令牌重复提交回放原登记，不再次扣减。
- `energy_lines` 在 `(ledger_id,event_id,equipment_id)` 上唯一，防止同一笔内重复划账；跨笔的“同一采样能量不重复划给同一设备”由服务层在投诉行锁内的余额校验保证，超额或无可解释余量时整笔退回（不插入任何明细）。
- 并发安全：所有能量登记先 `SELECT ... FOR UPDATE` 锁投诉行，READ COMMITTED 下两人同时提交会被串行化，后到者基于最新余额裁决并整笔退回。

本小型示例不附自动升级迁移器；修改列定义时需编写显式迁移，不能对已有库依赖create_all修改。已有库升级到本版需手动执行：

```sql
CREATE TABLE equipment (
  id INT PRIMARY KEY AUTO_INCREMENT,
  complaint_id INT NOT NULL,
  name VARCHAR(40) NOT NULL,
  kind VARCHAR(30) NOT NULL DEFAULT 'device',
  note VARCHAR(300) NOT NULL DEFAULT '',
  active TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY equipment_name_unique (complaint_id,name)
);
CREATE TABLE calibrations (
  id INT PRIMARY KEY AUTO_INCREMENT,
  complaint_id INT NOT NULL,
  equipment_id INT NOT NULL,
  event_id INT NOT NULL,
  note VARCHAR(300) NOT NULL DEFAULT '',
  UNIQUE KEY one_calibration_per_event (event_id),
  UNIQUE KEY calibration_natural_key (equipment_id,event_id)
);
CREATE TABLE energy_ledgers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  complaint_id INT NOT NULL,
  equipment_id INT NOT NULL,
  client_token VARCHAR(80) NOT NULL,
  amount FLOAT NOT NULL,
  note VARCHAR(400) NOT NULL DEFAULT '',
  reviewer VARCHAR(60) NOT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE KEY energy_ledger_idempotent (client_token),
  CHECK (amount >= 0)
);
CREATE TABLE energy_lines (
  id INT PRIMARY KEY AUTO_INCREMENT,
  ledger_id INT NOT NULL,
  complaint_id INT NOT NULL,
  equipment_id INT NOT NULL,
  event_id INT NOT NULL,
  amount FLOAT NOT NULL,
  UNIQUE KEY line_unique_within_ledger (ledger_id,event_id,equipment_id),
  CHECK (amount >= 0)
);
ALTER TABLE agreements ADD COLUMN energy_ledger_id INT NULL;
```
