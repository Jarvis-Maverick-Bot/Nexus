// translations.js — EN / ZH string resources
const T = {
  en: {
    // Nav
    nav_projects: 'Projects',
    nav_detail: 'Detail View',
    nav_gate: 'Gate Panel',
    nav_status: 'Status',
    nav_advisories: 'Advisories',
    nav_kickoff: 'Kickoff',

    // Topbar
    topbar_select_project: 'Select project…',
    topbar_version: 'v1.5',

    // Projects page
    proj_create: 'Create Project',
    proj_name: 'Project Name',
    proj_owner: 'Owner',
    proj_status: 'Status',
    proj_goal: 'Goal',
    proj_btn_create: '+ Create Project',
    proj_all: 'All Projects',
    proj_btn_refresh: '↻ Refresh',
    proj_ready: 'Ready. Enter project details above.',
    proj_no_projects: 'No projects yet. Create one above.',
    proj_err_name_owner: 'Name and Owner are required.',
    proj_err_load: 'Failed to load projects.',

    // Detail page
    detail_title: 'Project Detail',
    detail_load: 'Load',
    detail_refresh: 'Refresh',
    detail_select: '(select project…)',
    detail_artifacts: 'Artifacts',
    detail_add_artifact: 'Add / Update Artifact',
    detail_type: 'Type',
    detail_produced_by: 'Produced By',
    detail_content: 'Content',
    detail_btn_save: 'Save Artifact',
    detail_btn_approve: '✓ Approve',
    detail_btn_reject: '✗ Request Revision',
    detail_no_package: 'No acceptance package yet.',
    detail_accept_note: 'Your decision note',
    detail_artifact_select_type: 'Select a type above to edit.',
    detail_no_project: 'Select a project first.',
    detail_complete: 'Complete',
    detail_incomplete: 'Incomplete',

    // Gate page
    gate_title: 'Gate Confirmation',
    gate_task_id: 'Task ID',
    gate_load: 'Load Gate',
    gate_err_task: 'Enter a task ID first.',
    gate_pending: 'Gate: pending',
    gate_decision_note: 'Your decision',

    // Status page
    status_title: 'View Status',
    status_task_id: 'Task ID',
    status_btn: 'Get Status',
    status_list_project: 'Project ID',
    status_list_btn: 'List',
    status_err_task: 'Enter a task ID.',
    status_err_project: 'Enter a project ID.',

    // Advisories page
    adv_title: 'Advisories & Blockers',
    adv_select: '(select project…)',
    adv_refresh: 'Refresh',
    adv_blockers: 'Blockers',
    adv_advisories: 'Advisories',
    adv_resolve: 'Resolve',
    adv_dismiss: 'Dismiss',
    adv_empty: 'Select a project to view advisories.',
    adv_err_backend: 'Cannot reach PMO backend.',
    adv_no_active: 'No active advisories or blockers. ✓',

    // Kickoff page
    kick_title: 'Announce Kickoff',
    kick_task_title: 'Task Title',
    kick_project: 'Project',
    kick_select: '(select project…)',
    kick_desc: 'Description',
    kick_priority: 'Priority',
    kick_priority_0: 'P0 — Critical',
    kick_priority_1: 'P1 — High',
    kick_priority_2: 'P2 — Medium',
    kick_priority_3: 'P3 — Low',
    kick_assignee: 'Assignee',
    kick_actor: 'Your Name',
    kick_btn: '🚀 Announce Kickoff',
    kick_err_fields: 'Project, title, description, and your name are required.',

    // Status labels
    status_active: 'Active',
    status_on_hold: 'On Hold',
    status_closed: 'Closed',
    status_shutdown: 'Shutdown',

    // Artifact types
    artifact_scope: 'Scope',
    artifact_spec: 'Specification',
    artifact_arch: 'Architecture',
    artifact_testcase: 'Test Case',
    artifact_testreport: 'Test Report',
    artifact_guideline: 'Guideline',
    artifact_complete: 'Complete',
    artifact_missing: 'Missing',

    // Output messages
    out_creating: 'Creating…',
    out_saving: 'Saving…',
    out_loading: 'Loading…',
    out_announcing: 'Announcing…',

    // Language
    lang_toggle: 'EN / 中文',
  },

  zh: {
    // Nav
    nav_projects: '项目管理',
    nav_detail: '详情视图',
    nav_gate: '关卡面板',
    nav_status: '状态查询',
    nav_advisories: '预警信息',
    nav_kickoff: '任务发起',

    // Topbar
    topbar_select_project: '选择项目…',
    topbar_version: 'v1.5',

    // Projects page
    proj_create: '创建项目',
    proj_name: '项目名称',
    proj_owner: '负责人',
    proj_status: '状态',
    proj_goal: '项目目标',
    proj_btn_create: '+ 创建项目',
    proj_all: '全部项目',
    proj_btn_refresh: '↻ 刷新',
    proj_ready: '请填写上方项目信息。',
    proj_no_projects: '暂无项目，请在上方创建。',
    proj_err_name_owner: '名称和负责人为必填项。',
    proj_err_load: '加载项目失败。',

    // Detail page
    detail_title: '项目详情',
    detail_load: '加载',
    detail_refresh: '刷新',
    detail_select: '（选择项目…）',
    detail_artifacts: '制品',
    detail_add_artifact: '添加 / 更新制品',
    detail_type: '类型',
    detail_produced_by: '产出者',
    detail_content: '内容',
    detail_btn_save: '保存制品',
    detail_btn_approve: '✓ 批准',
    detail_btn_reject: '✗ 请求修订',
    detail_no_package: '暂无验收包。',
    detail_accept_note: '决策备注',
    detail_artifact_select_type: '选择上方类型进行编辑。',
    detail_no_project: '请先选择一个项目。',
    detail_complete: '已完成',
    detail_incomplete: '未完成',

    // Gate page
    gate_title: '关卡审批',
    gate_task_id: '任务 ID',
    gate_load: '加载关卡',
    gate_err_task: '请输入任务 ID。',
    gate_pending: '关卡状态：待审批',
    gate_decision_note: '决策备注',

    // Status page
    status_title: '状态查询',
    status_task_id: '任务 ID',
    status_btn: '查询状态',
    status_list_project: '项目 ID',
    status_list_btn: '列出任务',
    status_err_task: '请输入任务 ID。',
    status_err_project: '请输入项目 ID。',

    // Advisories page
    adv_title: '预警与阻塞',
    adv_select: '（选择项目…）',
    adv_refresh: '刷新',
    adv_blockers: '阻塞项',
    adv_advisories: '预警信息',
    adv_resolve: '解决',
    adv_dismiss: '关闭',
    adv_empty: '请选择一个项目查看预警。',
    adv_err_backend: '无法连接 PMO 后端。',
    adv_no_active: '暂无活跃预警或阻塞项。✓',

    // Kickoff page
    kick_title: '发起任务',
    kick_task_title: '任务名称',
    kick_project: '所属项目',
    kick_select: '（选择项目…）',
    kick_desc: '任务描述',
    kick_priority: '优先级',
    kick_priority_0: 'P0 — 紧急',
    kick_priority_1: 'P1 — 高',
    kick_priority_2: 'P2 — 中',
    kick_priority_3: 'P3 — 低',
    kick_assignee: '指派给',
    kick_actor: '您的姓名',
    kick_btn: '🚀 发起任务',
    kick_err_fields: '项目、名称、描述和您的姓名为必填项。',

    // Status labels
    status_active: '进行中',
    status_on_hold: '暂停',
    status_closed: '已关闭',
    status_shutdown: '已终止',

    // Artifact types
    artifact_scope: '范围',
    artifact_spec: '规格说明',
    artifact_arch: '架构设计',
    artifact_testcase: '测试用例',
    artifact_testreport: '测试报告',
    artifact_guideline: '操作指南',
    artifact_complete: '已完成',
    artifact_missing: '未完成',

    // Output messages
    out_creating: '创建中…',
    out_saving: '保存中…',
    out_loading: '加载中…',
    out_announcing: '发布中…',

    // Language
    lang_toggle: 'EN / 中文',
  }
};

// Current language
let _lang = localStorage.getItem('pmo_lang') || 'en';

function lang() { return _lang; }

function t(key) {
  return T[_lang]?.[key] ?? T['en']?.[key] ?? key;
}

function setLang(l) {
  _lang = l;
  localStorage.setItem('pmo_lang', l);
  applyTranslations();
}

function toggleLang() {
  setLang(_lang === 'en' ? 'zh' : 'en');
}

function applyTranslations() {
  // Apply data-i18n attributes — elements with this attr get their text replaced
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    el.textContent = t(key);
  });
  // Apply placeholders
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.getAttribute('data-i18n-placeholder');
    el.placeholder = t(key);
  });
}
