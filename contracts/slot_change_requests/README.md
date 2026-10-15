# 槽位变更请求（Slot Change Requests）

## 规则

任何人需要新增或修改槽位时，**不得直接修改 `contracts/slots.yaml`**。

### 新增槽位的流程

1. 在本目录下新建文件，命名格式：`YYYYMMDD_<提议槽位id>.md`（日期为提议日期）。
2. 文件内容必须包含：
   - 提议的槽位 id（英文 snake_case）
   - 完整字段（按照 `slots.yaml` 中的格式填写所有字段）
   - 为什么需要这个槽位
   - 哪一层（l1_redflag / l2_grading / l3_selfcare / l4_recommend / logging）会用到
   - 由谁提出（姓名或角色）
3. 提交后由项目负责人审查。
4. 批准后，槽位才会合并进 `contracts/slots.yaml` 并升版本号。
5. 未批准的请求文件保留在本目录中供追溯。

### 修改或删除已有槽位的流程

同样在本目录新建文件，命名格式：`YYYYMMDD_modify_<槽位id>.md`，说明修改/删除原因和影响。

## 空白模板

见同目录下的 `_template.md`。
