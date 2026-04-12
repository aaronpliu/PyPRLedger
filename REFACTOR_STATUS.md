# Review 多评审员重构 - 实施状态

## ✅ 已完成

### 1. 数据库层
- [x] 创建迁移脚本 `011_refactor_review_multi_reviewer.py`
- [x] 执行迁移（手动标记版本 + 数据迁移）
- [x] 新表结构验证通过
  - `pull_request_review_base`: 7 records
  - `pull_request_review_assignment`: 8 records

### 2. Models
- [x] 创建 `src/models/review.py`
  - `PullRequestReviewBase` - PR基础信息
  - `PullRequestReviewAssignment` - 评审员分配
- [x] 更新 `src/models/user.py` - 添加 `review_assignments` relationship
- [x] 更新 `src/models/__init__.py` - 导出新模型

### 3. Schemas
- [x] 创建 `src/schemas/review.py`
  - `ReviewBaseResponse` - Base review 响应
  - `ReviewerAssignmentResponse` - 评审员分配响应
  - `ReviewWithAssignmentsResponse` - 完整 review 响应（包含 reviewers 列表）
  - `ReviewListResponse` - 列表响应
  - `AssignReviewerRequest` - 分配评审员请求
  - `UpdateAssignmentStatusRequest` - 更新状态请求

### 4. Services
- [x] 创建 `src/services/multi_reviewer_service.py`
  - `get_reviews()` - 获取 review 列表（支持过滤和分页）
  - `get_review_by_id()` - 获取单个 review
  - `create_review_base()` - 创建 base 记录
  - `assign_reviewer()` - 分配评审员
  - `remove_reviewer()` - 移除评审员
  - `update_assignment_status()` - 更新分配状态
  - `delete_review()` - 删除 review（级联删除 assignments）

### 5. API Endpoints
- [x] 创建 `src/api/v1/endpoints/multi_reviewer.py`
  - `GET /api/v1/reviews-v2/` - 获取 review 列表
  - `GET /api/v1/reviews-v2/{id}` - 获取单个 review
  - `POST /api/v1/reviews-v2/{id}/assign` - 分配评审员
  - `DELETE /api/v1/reviews-v2/{id}/assign/{reviewer}` - 移除评审员
  - `PATCH /api/v1/reviews-v2/assignments/{id}/status` - 更新状态
  - `DELETE /api/v1/reviews-v2/{id}` - 删除 review
  - `GET /api/v1/reviews-v2/my-tasks` - 获取我的任务
- [x] 注册 router 到 `src/api/v1/api.py`

### 6. 测试
- [x] 后端服务测试通过
- [x] API endpoints 测试通过（返回正确的多评审员数据）
- [x] 创建 HTML 测试页面 `test_multi_reviewer.html`

---

## ⏳ 待完成

### 1. Schemas (高优先级)
需要创建新的 schemas 以支持多评审员：

**文件**: `src/schemas/review.py` (新建)
```python
class ReviewBaseResponse(BaseModel):
    """Base review info (from PullRequestReviewBase)"""
    id: int
    pull_request_id: str
    pull_request_commit_id: str | None
    project_key: str
    repository_slug: str
    source_filename: str | None
    source_branch: str
    target_branch: str
    git_code_diff: str | None
    ai_suggestions: dict | None
    pull_request_status: str
    metadata: dict | None
    created_date: datetime
    updated_date: datetime

class ReviewerAssignmentResponse(BaseModel):
    """Reviewer assignment info (from PullRequestReviewAssignment)"""
    id: int
    reviewer: str
    reviewer_info: dict | None  # Enriched user details
    assigned_by: str | None
    assigned_date: datetime | None
    assignment_status: str
    reviewer_comments: str | None
    created_date: datetime
    updated_date: datetime

class ReviewWithAssignmentsResponse(ReviewBaseResponse):
    """Complete review with all assignments"""
    reviewers: list[ReviewerAssignmentResponse]
    total_reviewers: int
    completed_reviewers: int
```

### 2. Services (高优先级)
需要重写 `src/services/review_service.py` 或使用新服务：

**关键方法**:
- `get_reviews()` - JOIN查询 base + assignments
- `get_review_by_id()` - 获取单个review及其所有评审员
- `create_review_base()` - 创建PR基础记录
- `assign_reviewer()` - 分配评审员（创建assignment）
- `remove_reviewer()` - 移除评审员
- `update_review_base()` - 更新PR基础信息
- `delete_review()` - 删除review（级联删除assignments）

### 3. API Endpoints (高优先级)
需要更新 `src/api/v1/endpoints/reviews.py`:

**现有 endpoints 需要修改**:
- `GET /api/v1/reviews` - 返回格式变化
- `GET /api/v1/reviews/{id}` - 包含 reviewers 列表
- `POST /api/v1/reviews` - 创建base + 可选的初始assignment
- `PUT /api/v1/reviews/{id}` - 更新base信息
- `DELETE /api/v1/reviews/{id}` - 删除整个review

**新增 endpoints**:
- `POST /api/v1/reviews/{id}/assign` - 分配评审员
- `DELETE /api/v1/reviews/{id}/assign/{reviewer}` - 移除评审员
- `GET /api/v1/reviews/{id}/reviewers` - 获取所有评审员
- `GET /api/v1/reviews/my-tasks` - 获取当前用户的任务

### 4. Frontend (中优先级)
需要更新 Vue 组件：

**ReviewListView.vue**:
- 显示多个评审员（tags而非单行）
- Review Admin可以批量管理评审员
- 普通reviewer只看到自己的任务

**ReviewDetailView.vue**:
- 显示所有评审员列表
- 显示每个评审员的状态和评分
- 评分功能保持不变（仍使用PullRequestScore）

### 5. 清理 (低优先级)
- 弃用旧的 `PullRequestReview` model
- 删除 `pull_request_review` 旧表（保留一段时间作为备份）
- 更新文档

---

## 🎯 下一步行动

建议按以下顺序实施：

1. **创建新 Schemas** (30分钟)
2. **重写 Review Service** (2-3小时)
3. **更新 API Endpoints** (2-3小时)
4. **测试后端API** (1小时)
5. **更新 Frontend** (3-4小时)
6. **端到端测试** (1小时)

**预计总时间**: 10-12小时

---

## 💡 注意事项

1. **向后兼容**: 旧表 `pull_request_review` 暂时保留，直到新系统稳定
2. **数据迁移**: 已完成，8条记录已迁移
3. **评分系统**: 不受影响，仍使用 `PullRequestScore` 表
4. **缓存策略**: 需要更新Redis key结构

---

## 🔍 当前数据库状态

```sql
-- 新表结构
pull_request_review_base (7 records)
├── id (PK)
├── pull_request_id
├── pull_request_commit_id
├── project_key (FK → project)
├── repository_slug (FK → repository)
├── source_filename
├── source_branch
├── target_branch
├── git_code_diff (TEXT)
├── ai_suggestions (JSON)
├── pull_request_status
├── metadata (JSON)
├── created_date
└── updated_date

pull_request_review_assignment (8 records)
├── id (PK)
├── review_base_id (FK → pull_request_review_base.id)
├── reviewer (FK → user.username)
├── assigned_by (FK → user.username)
├── assigned_date
├── assignment_status
├── reviewer_comments (TEXT)
├── created_date
└── updated_date

-- 旧表（备份）
pull_request_review (8 records) - 保留作为备份
```

---

**准备继续实施吗？我可以从 Schemas 开始！** 🚀
