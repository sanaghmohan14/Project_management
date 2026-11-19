/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class ProjectManageDashboard extends Component {
    static template = "project_manage.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("dashboardRoot");

        // Load saved theme or auto-detect from Odoo's native dark mode / system preference
        const savedTheme = localStorage.getItem("pm_dashboard_theme");
        const isOdooDark = typeof document !== 'undefined' && (
            document.body.classList.contains("o_dark_theme") ||
            document.documentElement.getAttribute("data-color-scheme") === "dark" ||
            (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches)
        );
        const initialDark = savedTheme !== null ? (savedTheme === "dark") : Boolean(isOdooDark);

        const actionParams = this.props?.action?.params || {};
        const actionContext = this.props?.action?.context || this.props?.context || {};
        const defaultView = actionParams.default_main_view || actionContext.default_main_view || 'home';

        onWillUpdateProps((nextProps) => {
            const nextActionParams = nextProps?.action?.params || {};
            const nextActionContext = nextProps?.action?.context || nextProps?.context || {};
            const nextView = nextActionParams.default_main_view || nextActionContext.default_main_view;
            if (nextView && nextView !== this.state.activeMainView) {
                this.setActiveTab(nextView);
                if (nextView === 'projects') {
                    this.scrollToProjectsTable();
                }
            }
        });

        onMounted(() => {
            if (this.state.activeMainView === 'projects') {
                this.scrollToProjectsTable();
            }
        });

        this.state = useState({
            loading: true,
            darkMode: initialDark,
            isMobile: typeof window !== 'undefined' ? (window.innerWidth < 992) : false,
            activeMainView: defaultView,  // 'home', 'projects', 'approvals', 'scopes', 'calendar'
            projectStatusFilter: 'all',  // 'all', 'running', 'on_hold', 'completed'
            projectRiskFilter: 'all',    // 'all', 'low', 'medium', 'high'
            projectHealthFilter: 'all',  // 'all', 'good', 'fair', 'poor'
            projectConditionFilter: 'all', // 'all', 'ahead', 'on_plan', 'behind', 'overdue'
            projectDeliveryFilter: 'all',  // 'all', 'on_time'
            projectSearchFilter: '',       // search query string
            projectCardsWizardOpen: false,
            projectCardsWizardTitle: "Projects",
            projectCardsWizardSubtitle: "",
            projectCardsWizardFilterType: "all",
            projectCardsWizardFilterValue: "",
            projectCardsWizardSearch: "",
            calendarTimeFilter: 'today',  // 'today', 'tomorrow', 'week', 'month', 'all'
            calendarViewMode: 'week_strip',   // 'week_strip', 'month', 'agenda'
            calendarCategoryFilter: 'all', // 'all', 'documentation', 'implementation'
            calendarTypeFilter: 'task',  // strictly tasks only
            calendarStatusFilter: 'all', // 'all', 'overdue', 'in_progress', 'done'
            calendarYear: new Date().getFullYear(),
            calendarMonth: new Date().getMonth(), // 0-11
            calendarDate: new Date().getDate(),
            calendarTaskFilterScope: 'day', // 'day' (selected date), 'week', 'month', 'overdue'
            calendarSearchQuery: "",
            selectedTeamId: null,
            activeRoleView: null,
            selectedProjectId: null,
            projectScopesLoading: false,
            projectScopesData: null,
            activeCategoryFilter: 'all',  // 'all', 'documentation', 'implementation'
            activeStatusFilter: 'all',    // 'all', 'completed', 'in_progress', 'pending', 'overdue'
            selectedScopeName: null,      // specific scope filter if clicked
            searchQuery: "",
            editingScopeId: null,
            editRowData: {},
            scopeWizardOpen: false,
            wizardData: {},
            projectWizardOpen: false,
            projectWizardLoading: false,
            projectFormData: null,
            newProjectData: {
                name: "",
                priority: "0",
                partner_id: "",
                client_coordinator_id: "",
                date_start: "",
                date_end: "",
                tag_ids: [],
                team_id: "",
                manager_id: "",
                team_lead_id: "",
                project_coordinator_id: "",
                consultant_ids: [],
                load_standard_scopes: true,
                import_file: null,
                import_filename: "",
            },
            savingNewProject: false,
            editProjectWizardOpen: false,
            editProjectWizardLoading: false,
            savingEditProject: false,
            editProjectData: null,
            scopeDetailWizardOpen: false,
            scopeDetailLoading: false,
            scopeDetailData: null,
            projectDetailWizardOpen: false,
            projectDetailLoading: false,
            projectDetailData: null,
            startingProject: false,
            bulkWizardOpen: false,
            bulkData: {
                target: 'scope',
                scope_name_filter: '',
                responsible_id: '',
                responsible_ids: [],
                start_date: '',
                end_date: '',
                state: '',
                category: '',
            },
            savingScope: false,
            taskTab: 'pending', // 'pending', 'completed', 'overdue', 'waiting_approval', 'all'
            taskCategoryFilter: 'all', // 'all', 'documentation', 'implementation'
            taskPriorityFilter: 'all', // 'all', 'starred', '3', '2', '1', '0'
            taskConsultantFilter: 'all', // 'all' or consultant id
            taskProjectFilter: 'all', // 'all' or project id
            taskSearchQuery: "",
            data: {
                company_name: "Benac Business Solutions",
                current_date_str: "Loading...",
                user_info: {
                    id: null,
                    name: "Loading...",
                    role_code: "consultant",
                    role_name: "Consultant",
                    role_badge: "💻 Consultant",
                    role_badge_class: "pm-role-consultant",
                    is_admin: false,
                    is_ceo: false,
                    is_vp: false,
                    is_manager: false,
                    is_team_lead: false,
                    is_consultant: true,
                    is_executive: false,
                    can_approve: false,
                    can_create_project: false,
                    can_see_all_teams: false,
                },
                user_team_name: "",
                approvals_summary: {
                    pending_my_approval_count: 0,
                    all_pending_count: 0,
                    pending_items: [],
                },
                tasks_hub: {
                    role_code: "consultant",
                    title: "Tasks Hub",
                    subtitle: "Track pending deliverables and completed tasks",
                    role_label: "Tasks",
                    total_count: 0,
                    pending_count: 0,
                    completed_count: 0,
                    overdue_count: 0,
                    waiting_approval_count: 0,
                    available_consultants: [],
                    available_projects: [],
                    tasks: [],
                },
                consultant_workspace: {
                    my_total_tasks: 0,
                    my_todo_count: 0,
                    my_inprogress_count: 0,
                    my_waiting_approval_count: 0,
                    my_done_count: 0,
                    my_rejected_count: 0,
                    my_tasks: [],
                },
                top_performers: [],
                total_projects: 0,
                total_teams: 0,
                total_consultants: 0,
                running_count: 0,
                completed_count: 0,
                on_hold_count: 0,
                not_started_count: 0,
                health_good_count: 0,
                health_fair_count: 0,
                health_poor_count: 0,
                overall_health_score: 0,
                overall_health_label: "Good",
                risk_low_count: 0,
                risk_med_count: 0,
                risk_high_count: 0,
                risk_status_label: "Low risk",
                on_time_pct: 0,
                avg_progress: 0,
                condition_ahead_count: 0,
                condition_on_plan_count: 0,
                condition_behind_count: 0,
                condition_overdue_count: 0,
                cond_max_count: 5,
                donut_good_dash: "238.8 238.8",
                donut_good_offset: "0",
                donut_fair_dash: "0 238.8",
                donut_fair_offset: "0",
                donut_poor_dash: "0 238.8",
                donut_poor_offset: "0",
                risk_needle_angle: -50,
                teams: [],
                all_teams_filter: [],
                projects: [],
                calendar_events: [],
                consultant_task_stats: {
                    total: 0,
                    completed: 0,
                    not_completed: 0,
                    overdue: 0,
                    pending: 0,
                    waiting_approval: 0,
                    completion_pct: 0,
                    not_completed_pct: 0,
                    projects_breakdown: [],
                },
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });

        const checkMobile = () => {
            if (typeof window !== 'undefined') {
                const mobile = window.innerWidth < 992;
                if (this.state.isMobile !== mobile) {
                    this.state.isMobile = mobile;
                }
            }
        };
        this._onResize = checkMobile;
        if (typeof window !== 'undefined') {
            window.addEventListener('resize', this._onResize);
        }
        onWillUnmount(() => {
            if (typeof window !== 'undefined' && this._onResize) {
                window.removeEventListener('resize', this._onResize);
            }
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const kwargs = {};
            if (this.state.selectedTeamId) {
                kwargs.team_id = this.state.selectedTeamId;
            }
            if (this.state.selectedProjectId) {
                kwargs.project_id = this.state.selectedProjectId;
            }
            if (this.state.activeRoleView) {
                kwargs.view_as_role = this.state.activeRoleView;
            }
            const res = await this.orm.call("project.manage", "get_dashboard_data", [], kwargs);
            if (res) {
                this.state.data = res;
            }
        } catch (error) {
            console.error("Failed to load project dashboard data:", error);
            if (this.notification) {
                this.notification.add("Could not refresh dashboard data.", { type: "danger" });
            }
        } finally {
            this.state.loading = false;
        }
    }

    async switchRoleView(role) {
        this.state.activeRoleView = role;
        await this.loadData();
    }

    toggleTheme() {
        this.state.darkMode = !this.state.darkMode;
        localStorage.setItem("pm_dashboard_theme", this.state.darkMode ? "dark" : "light");
    }

    async onSelectTeam(teamId) {
        if (!this.state.data.user_info.can_see_all_teams) {
            return;
        }
        if (this.state.selectedTeamId === teamId) {
            this.state.selectedTeamId = null;
        } else {
            this.state.selectedTeamId = teamId;
        }
        this.state.selectedProjectId = null;
        this.state.projectScopesData = null;
        await this.loadData();
    }

    async onProjectSelectChange(ev) {
        const val = ev.target.value;
        const projId = val ? parseInt(val) : null;
        this.state.selectedProjectId = projId;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        if (projId) {
            await Promise.all([
                this.loadData(),
                this.loadProjectScopes(projId),
            ]);
        } else {
            this.state.projectScopesData = null;
            await this.loadData();
        }
    }

    async clearProjectFilter() {
        this.state.selectedProjectId = null;
        this.state.projectScopesData = null;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        await this.loadData();
    }

    async onSelectProject(projectId, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        if (this.state.selectedProjectId === projectId) {
            this.state.selectedProjectId = null;
            this.state.projectScopesData = null;
            await this.loadData();
            return;
        }
        this.state.selectedProjectId = projectId;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        await Promise.all([
            this.loadData(),
            this.loadProjectScopes(projectId),
        ]);
    }

    async loadProjectScopes(projectId) {
        this.state.projectScopesLoading = true;
        try {
            const res = await this.orm.call("project.manage", "get_project_scopes_dashboard", [projectId]);
            this.state.projectScopesData = res;
        } catch (err) {
            console.error("Failed to load project scopes:", err);
            if (this.notification) {
                this.notification.add("Could not load scopes for this project.", { type: "danger" });
            }
        } finally {
            this.state.projectScopesLoading = false;
        }
    }

    setCategoryFilter(cat) {
        this.state.activeCategoryFilter = cat;
    }

    setStatusFilter(status) {
        this.state.activeStatusFilter = status;
    }

    setScopeNameFilter(scopeName) {
        if (this.state.selectedScopeName === scopeName) {
            this.state.selectedScopeName = null;
        } else {
            this.state.selectedScopeName = scopeName;
        }
    }

    onScopeSelectChange(ev) {
        const val = ev.target.value;
        this.state.selectedScopeName = val ? val : null;
    }

    onSearchChange(ev) {
        this.state.searchQuery = ev.target.value.toLowerCase().trim();
    }

    clearFilters() {
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
    }

    get filteredScopes() {
        if (!this.state.projectScopesData || !this.state.projectScopesData.scopes) {
            return [];
        }
        let list = this.state.projectScopesData.scopes;

        // Filter by category
        if (this.state.activeCategoryFilter === 'documentation') {
            list = list.filter(s => s.category.toLowerCase().includes('doc'));
        } else if (this.state.activeCategoryFilter === 'implementation') {
            list = list.filter(s => s.category.toLowerCase().includes('imp'));
        }

        // Filter by status color
        if (this.state.activeStatusFilter === 'completed') {
            list = list.filter(s => s.status_color === 'green');
        } else if (this.state.activeStatusFilter === 'in_progress') {
            list = list.filter(s => s.status_color === 'blue');
        } else if (this.state.activeStatusFilter === 'pending') {
            list = list.filter(s => s.status_color === 'yellow');
        } else if (this.state.activeStatusFilter === 'overdue') {
            list = list.filter(s => s.status_color === 'red');
        }

        // Filter by specific Scope
        if (this.state.selectedScopeName) {
            list = list.filter(s => s.scope_name === this.state.selectedScopeName);
        }

        // Search query
        if (this.state.searchQuery) {
            const q = this.state.searchQuery;
            list = list.filter(s => 
                (s.item_id && s.item_id.toLowerCase().includes(q)) ||
                (s.name && s.name.toLowerCase().includes(q)) ||
                (s.scope_name && s.scope_name.toLowerCase().includes(q)) ||
                (s.responsible_name && s.responsible_name.toLowerCase().includes(q))
            );
        }

        return list;
    }

    // ==================== UNIVERSAL TASKS HUB METHODS & GETTER ====================
    setTaskTab(tab) {
        this.state.taskTab = tab;
    }

    setTaskCategoryFilter(cat) {
        this.state.taskCategoryFilter = cat;
    }

    setTaskPriorityFilter(ev) {
        this.state.taskPriorityFilter = ev.target.value;
    }

    setTaskConsultantFilter(ev) {
        this.state.taskConsultantFilter = ev.target.value;
    }

    setTaskProjectFilter(ev) {
        this.state.taskProjectFilter = ev.target.value;
    }

    onTaskSearchChange(ev) {
        this.state.taskSearchQuery = ev.target.value.toLowerCase().trim();
    }

    clearTaskFilters() {
        this.state.taskTab = 'pending';
        this.state.taskCategoryFilter = 'all';
        this.state.taskPriorityFilter = 'all';
        this.state.taskConsultantFilter = 'all';
        this.state.taskProjectFilter = 'all';
        this.state.taskSearchQuery = '';
    }

    scrollToApprovals() {
        if (!this.state.isMobile && typeof document !== 'undefined') {
            const el = document.getElementById("pm-approval-section");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                return;
            }
        }
        this.setActiveTab('approvals');
    }

    scrollToTasksHub() {
        if (!this.state.isMobile && typeof document !== 'undefined') {
            const el = document.getElementById("pm-tasks-hub");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                return;
            }
        }
        this.setActiveTab('scopes');
    }

    get filteredTasks() {
        const hub = this.state.data.tasks_hub;
        if (!hub || !hub.tasks) {
            return [];
        }
        let list = hub.tasks;

        // 1. Tab Filter
        if (this.state.taskTab === 'pending') {
            list = list.filter(t => t.is_pending);
        } else if (this.state.taskTab === 'completed') {
            list = list.filter(t => t.is_completed);
        } else if (this.state.taskTab === 'overdue') {
            list = list.filter(t => t.is_overdue && t.is_pending);
        } else if (this.state.taskTab === 'waiting_approval') {
            list = list.filter(t => ['pending_tl', 'pending_pm', 'pending_vp', 'pending_ceo'].includes(t.approval_state));
        }

        // 2. Category Filter
        if (this.state.taskCategoryFilter === 'documentation') {
            list = list.filter(t => (t.category || '').toLowerCase().includes('doc'));
        } else if (this.state.taskCategoryFilter === 'implementation') {
            list = list.filter(t => (t.category || '').toLowerCase().includes('imp'));
        }

        // 3. Priority Filter (Star)
        if (this.state.taskPriorityFilter && this.state.taskPriorityFilter !== 'all') {
            if (this.state.taskPriorityFilter === 'starred') {
                list = list.filter(t => (Number(t.priority) || 0) > 0);
            } else {
                const targetPri = String(this.state.taskPriorityFilter);
                list = list.filter(t => String(t.priority || '0') === targetPri);
            }
        }

        // 4. Consultant Filter
        if (this.state.taskConsultantFilter && this.state.taskConsultantFilter !== 'all') {
            const filterId = Number(this.state.taskConsultantFilter);
            list = list.filter(t =>
                (Array.isArray(t.responsible_ids) && t.responsible_ids.includes(filterId)) ||
                Number(t.responsible_id) === filterId ||
                String(t.responsible_id) === String(this.state.taskConsultantFilter)
            );
        }

        // 5. Project Filter
        if (this.state.taskProjectFilter && this.state.taskProjectFilter !== 'all') {
            list = list.filter(t => String(t.project_id) === String(this.state.taskProjectFilter));
        }

        // 6. Search Query
        if (this.state.taskSearchQuery) {
            const q = this.state.taskSearchQuery;
            list = list.filter(t =>
                (t.name && t.name.toLowerCase().includes(q)) ||
                (t.code && t.code.toLowerCase().includes(q)) ||
                (t.project_name && t.project_name.toLowerCase().includes(q)) ||
                (t.responsible_name && t.responsible_name.toLowerCase().includes(q))
            );
        }

        // High priority task on top (3 -> 2 -> 1 -> 0)
        list = [...list].sort((a, b) => {
            const pA = Number(a.priority) || 0;
            const pB = Number(b.priority) || 0;
            if (pB !== pA) {
                return pB - pA;
            }
            return 0;
        });

        return list;
    }

    // ==================== 5-VIEW TAB NAVIGATION METHODS ====================
    setActiveTab(tab) {
        this.state.activeMainView = tab;
        if (tab === 'scopes' && !this.state.selectedProjectId) {
            const projs = (this.state.data && this.state.data.projects) || [];
            if (projs.length > 0) {
                this.selectProjectForScopes(projs[0].id);
            }
        }
        if (this.rootRef && this.rootRef.el) {
            this.rootRef.el.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    isTabActive(tab) {
        const current = this.state.activeMainView || 'home';
        if (tab === 'home') {
            return current === 'home' || current === 'dashboard';
        }
        if (tab === 'scopes') {
            return current === 'scopes' || current === 'tasks';
        }
        return current === tab;
    }

    isSectionVisible(section) {
        if (!this.state.isMobile) {
            // Desktop view:
            if (this.state.activeMainView === 'calendar') {
                return section === 'calendar';
            }
            if (section === 'calendar') {
                return false;
            }
            return true;
        }
        // Mobile view: strictly show only the active tab (home, projects, approvals, scopes, calendar)
        return this.isTabActive(section);
    }

    async selectProjectForScopes(projectId) {
        if (!projectId) return;
        this.state.selectedProjectId = projectId;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        await this.loadProjectScopes(projectId);
    }

    openProjectScopesTab(projectId, ev) {
        if (ev) ev.stopPropagation();
        this.setActiveTab('scopes');
        this.selectProjectForScopes(projectId);
    }

    setProjectStatusFilter(filter) {
        this.state.projectStatusFilter = filter;
    }

    get filteredProjects() {
        let projs = (this.state.data && this.state.data.projects) || [];
        if (this.state.selectedTeamId) {
            const tm = this.state.data?.teams?.find(t => String(t.id) === String(this.state.selectedTeamId));
            if (tm && Array.isArray(tm.project_ids) && tm.project_ids.length > 0) {
                projs = projs.filter(p => tm.project_ids.includes(p.id));
            } else if (typeof this.state.selectedTeamId === 'string' && this.state.selectedTeamId.startsWith('lead_')) {
                const leadId = parseInt(this.state.selectedTeamId.replace('lead_', ''), 10);
                projs = projs.filter(p =>
                    p.team_lead_id === leadId ||
                    (tm && p.team_lead_name && tm.lead_name && p.team_lead_name.trim().toLowerCase() === tm.lead_name.trim().toLowerCase()) ||
                    (tm && p.team_name && tm.name && p.team_name.trim().toLowerCase() === tm.name.trim().toLowerCase())
                );
            } else {
                const tId = parseInt(this.state.selectedTeamId, 10);
                projs = projs.filter(p =>
                    p.team_id === tId ||
                    (tm && tm.team_lead_id && p.team_lead_id === tm.team_lead_id) ||
                    (tm && p.team_lead_name && tm.lead_name && p.team_lead_name.trim().toLowerCase() === tm.lead_name.trim().toLowerCase()) ||
                    (tm && p.team_name && tm.name && p.team_name.trim().toLowerCase() === tm.name.trim().toLowerCase())
                );
            }
        }
        if (this.state.projectStatusFilter && this.state.projectStatusFilter !== 'all') {
            if (this.state.projectStatusFilter === 'high_risk') {
                projs = projs.filter(p => p.risk_level === 'high');
            } else {
                projs = projs.filter(p => p.running_status === this.state.projectStatusFilter);
            }
        }
        if (this.state.projectRiskFilter && this.state.projectRiskFilter !== 'all') {
            projs = projs.filter(p => p.risk_level === this.state.projectRiskFilter);
        }
        if (this.state.projectHealthFilter && this.state.projectHealthFilter !== 'all') {
            projs = projs.filter(p => p.health === this.state.projectHealthFilter);
        }
        if (this.state.projectConditionFilter && this.state.projectConditionFilter !== 'all') {
            projs = projs.filter(p => p.condition === this.state.projectConditionFilter);
        }
        if (this.state.projectDeliveryFilter === 'on_time') {
            projs = projs.filter(p => p.condition === 'ahead' || p.condition === 'on_plan');
        }
        if (this.state.projectSearchFilter && this.state.projectSearchFilter.trim()) {
            const q = this.state.projectSearchFilter.trim().toLowerCase();
            projs = projs.filter(p =>
                (p.name && p.name.toLowerCase().includes(q)) ||
                (p.client_name && p.client_name.toLowerCase().includes(q))
            );
        }
        return projs;
    }

    get isProjectFilterActive() {
        return Boolean(
            (this.state.projectStatusFilter && this.state.projectStatusFilter !== 'all') ||
            (this.state.projectRiskFilter && this.state.projectRiskFilter !== 'all') ||
            (this.state.projectHealthFilter && this.state.projectHealthFilter !== 'all') ||
            (this.state.projectConditionFilter && this.state.projectConditionFilter !== 'all') ||
            (this.state.projectDeliveryFilter && this.state.projectDeliveryFilter !== 'all') ||
            (this.state.selectedTeamId) ||
            (this.state.projectSearchFilter && this.state.projectSearchFilter.trim())
        );
    }

    get activeProjectFilterLabel() {
        const parts = [];
        if (this.state.selectedTeamId) {
            const tm = this.state.data?.teams?.find(t => String(t.id) === String(this.state.selectedTeamId));
            parts.push(tm ? tm.name : 'Team');
        }
        if (this.state.projectStatusFilter && this.state.projectStatusFilter !== 'all') {
            const statusMap = {
                running: 'Running',
                completed: 'Completed',
                on_hold: 'On Hold',
                not_started: 'Not Started',
                high_risk: 'High Risk',
            };
            parts.push(statusMap[this.state.projectStatusFilter] || this.state.projectStatusFilter);
        }
        if (this.state.projectRiskFilter && this.state.projectRiskFilter !== 'all') {
            const riskMap = {
                low: 'Low Risk',
                medium: 'Medium Risk',
                high: 'High Risk',
            };
            parts.push(riskMap[this.state.projectRiskFilter] || `${this.state.projectRiskFilter.toUpperCase()} Risk`);
        }
        if (this.state.projectHealthFilter && this.state.projectHealthFilter !== 'all') {
            const healthMap = {
                good: 'Good Health',
                fair: 'Fair Health',
                poor: 'Poor Health',
            };
            parts.push(healthMap[this.state.projectHealthFilter] || `Health: ${this.state.projectHealthFilter}`);
        }
        if (this.state.projectConditionFilter && this.state.projectConditionFilter !== 'all') {
            const condMap = {
                ahead: 'Ahead of Plan',
                on_plan: 'On Plan',
                behind: 'Behind Plan',
                overdue: 'Overdue',
            };
            parts.push(condMap[this.state.projectConditionFilter] || this.state.projectConditionFilter);
        }
        if (this.state.projectDeliveryFilter === 'on_time') {
            parts.push('On-Time Delivery');
        }
        return parts.join(' · ') || 'Filtered Projects';
    }

    clearProjectFilters(ev) {
        if (ev) ev.stopPropagation();
        this.state.projectStatusFilter = 'all';
        this.state.projectRiskFilter = 'all';
        this.state.projectHealthFilter = 'all';
        this.state.projectConditionFilter = 'all';
        this.state.projectDeliveryFilter = 'all';
        this.state.selectedTeamId = null;
        this.state.projectSearchFilter = '';
    }

    get wizardFilteredProjects() {
        let projs = (this.state.data && this.state.data.projects) || [];
        const fType = this.state.projectCardsWizardFilterType;
        const fVal = this.state.projectCardsWizardFilterValue;

        if (fType === 'running_status' && fVal && fVal !== 'all') {
            projs = projs.filter(p => p.running_status === fVal);
        } else if (fType === 'risk' && fVal && fVal !== 'all') {
            projs = projs.filter(p => p.risk_level === fVal);
        } else if (fType === 'health' && fVal && fVal !== 'all') {
            projs = projs.filter(p => p.health === fVal);
        } else if (fType === 'condition' && fVal && fVal !== 'all') {
            projs = projs.filter(p => p.condition === fVal);
        } else if (fType === 'on_time') {
            projs = projs.filter(p => p.condition === 'ahead' || p.condition === 'on_plan');
        } else if (fType === 'team' && fVal) {
            const tm = this.state.data?.teams?.find(t => String(t.id) === String(fVal));
            if (tm && Array.isArray(tm.project_ids) && tm.project_ids.length > 0) {
                projs = projs.filter(p => tm.project_ids.includes(p.id));
            } else if (typeof fVal === 'string' && fVal.startsWith('lead_')) {
                const leadId = parseInt(fVal.replace('lead_', ''), 10);
                projs = projs.filter(p =>
                    p.team_lead_id === leadId ||
                    (tm && p.team_lead_name && tm.lead_name && p.team_lead_name.trim().toLowerCase() === tm.lead_name.trim().toLowerCase()) ||
                    (tm && p.team_name && tm.name && p.team_name.trim().toLowerCase() === tm.name.trim().toLowerCase())
                );
            } else {
                const tId = parseInt(fVal, 10);
                projs = projs.filter(p =>
                    p.team_id === tId ||
                    (tm && tm.team_lead_id && p.team_lead_id === tm.team_lead_id) ||
                    (tm && p.team_lead_name && tm.lead_name && p.team_lead_name.trim().toLowerCase() === tm.lead_name.trim().toLowerCase()) ||
                    (tm && p.team_name && tm.name && p.team_name.trim().toLowerCase() === tm.name.trim().toLowerCase())
                );
            }
        }

        if (this.state.projectCardsWizardSearch && this.state.projectCardsWizardSearch.trim()) {
            const q = this.state.projectCardsWizardSearch.trim().toLowerCase();
            projs = projs.filter(p =>
                (p.name && p.name.toLowerCase().includes(q)) ||
                (p.client_name && p.client_name.toLowerCase().includes(q)) ||
                (p.team_name && p.team_name.toLowerCase().includes(q))
            );
        }
        return projs;
    }

    openProjectCardsWizard(filterType = 'all', filterValue = '', title = '', subtitle = '', ev = null) {
        if (ev) ev.stopPropagation();
        this.state.projectCardsWizardFilterType = filterType;
        this.state.projectCardsWizardFilterValue = filterValue;
        this.state.projectCardsWizardTitle = title || "Projects";
        this.state.projectCardsWizardSubtitle = subtitle || "";
        this.state.projectCardsWizardSearch = "";
        this.state.projectCardsWizardOpen = true;
    }

    closeProjectCardsWizard() {
        this.state.projectCardsWizardOpen = false;
        this.state.projectCardsWizardSearch = "";
    }

    openProjectScopesFromCardWizard(projectId) {
        this.closeProjectCardsWizard();
        this.openProjectScopesTab(projectId);
    }

    openEditProjectFromCardWizard(projectId) {
        this.closeProjectCardsWizard();
        this.openEditProjectWizard(projectId);
    }

    openProjectDetailFromCardWizard(projectId) {
        this.closeProjectCardsWizard();
        this.openProjectDetailWizard(projectId);
    }

    // ==================== CALENDAR VIEW METHODS & GETTERS ====================
    setMainView(view) {
        this.setActiveTab(view);
    }

    setCalendarTimeFilter(filter) {
        this.state.calendarTimeFilter = filter;
        const now = new Date();
        if (filter === 'today') {
            this.state.calendarYear = now.getFullYear();
            this.state.calendarMonth = now.getMonth();
            this.state.calendarDate = now.getDate();
        } else if (filter === 'tomorrow') {
            const tom = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
            this.state.calendarYear = tom.getFullYear();
            this.state.calendarMonth = tom.getMonth();
            this.state.calendarDate = tom.getDate();
        } else if (filter === 'week') {
            this.state.calendarYear = now.getFullYear();
            this.state.calendarMonth = now.getMonth();
            this.state.calendarDate = now.getDate();
            this.state.calendarViewMode = 'week';
        } else if (filter === 'month') {
            this.state.calendarYear = now.getFullYear();
            this.state.calendarMonth = now.getMonth();
            this.state.calendarDate = now.getDate();
            this.state.calendarViewMode = 'month';
        }
    }

    setCalendarViewMode(mode) {
        this.state.calendarViewMode = mode;
    }

    setCalendarCategoryFilter(cat) {
        this.state.calendarCategoryFilter = cat;
    }

    setCalendarTypeFilter(type) {
        this.state.calendarTypeFilter = type;
    }

    setCalendarStatusFilter(status) {
        this.state.calendarStatusFilter = status;
    }

    calendarPrev() {
        if (this.state.calendarViewMode === 'week_strip') {
            this.calendarPrevDay();
        } else if (this.state.calendarViewMode === 'month') {
            if (this.state.calendarMonth === 0) {
                this.state.calendarMonth = 11;
                this.state.calendarYear -= 1;
            } else {
                this.state.calendarMonth -= 1;
            }
        } else if (this.state.calendarViewMode === 'week') {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate - 7);
            this.state.calendarYear = cur.getFullYear();
            this.state.calendarMonth = cur.getMonth();
            this.state.calendarDate = cur.getDate();
        } else {
            this.calendarPrevDay();
        }
    }

    calendarNext() {
        if (this.state.calendarViewMode === 'week_strip') {
            this.calendarNextDay();
        } else if (this.state.calendarViewMode === 'month') {
            if (this.state.calendarMonth === 11) {
                this.state.calendarMonth = 0;
                this.state.calendarYear += 1;
            } else {
                this.state.calendarMonth += 1;
            }
        } else if (this.state.calendarViewMode === 'week') {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate + 7);
            this.state.calendarYear = cur.getFullYear();
            this.state.calendarMonth = cur.getMonth();
            this.state.calendarDate = cur.getDate();
        } else {
            this.calendarNextDay();
        }
    }

    calendarPrevDay() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate - 1);
        this.state.calendarYear = cur.getFullYear();
        this.state.calendarMonth = cur.getMonth();
        this.state.calendarDate = cur.getDate();
    }

    calendarNextDay() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate + 1);
        this.state.calendarYear = cur.getFullYear();
        this.state.calendarMonth = cur.getMonth();
        this.state.calendarDate = cur.getDate();
    }

    calendarPrevWeek() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate - 7);
        this.state.calendarYear = cur.getFullYear();
        this.state.calendarMonth = cur.getMonth();
        this.state.calendarDate = cur.getDate();
    }

    calendarNextWeek() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate + 7);
        this.state.calendarYear = cur.getFullYear();
        this.state.calendarMonth = cur.getMonth();
        this.state.calendarDate = cur.getDate();
    }

    calendarToday() {
        const now = new Date();
        this.state.calendarYear = now.getFullYear();
        this.state.calendarMonth = now.getMonth();
        this.state.calendarDate = now.getDate();
        this.state.calendarTaskFilterScope = 'day';
        this.state.calendarTimeFilter = 'today';
    }

    selectCalendarDate(day) {
        if (!day) return;
        this.state.calendarYear = day.year;
        this.state.calendarMonth = day.month;
        this.state.calendarDate = day.dayNum;
        this.state.calendarTaskFilterScope = 'day';
    }

    get calendarSelectedDateIso() {
        const pad = (n) => String(n).padStart(2, "0");
        return `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}-${pad(this.state.calendarDate)}`;
    }

    get calendarSelectedDateTitle() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return `${dayNames[cur.getDay()]}, ${monthNames[cur.getMonth()]} ${cur.getDate()}`;
    }

    get calendarSelectedDateFullTitle() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        return `${dayNames[cur.getDay()]}, ${cur.getDate()} ${monthNames[cur.getMonth()]} ${cur.getFullYear()}`;
    }

    get calendarIsSelectedDateToday() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        return this.calendarSelectedDateIso === todayIso;
    }

    get calendarWeekStripDays() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayOfWeek = cur.getDay(); // 0 is Sun, 1 is Mon...
        const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
        const monday = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);

        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const selectedIso = `${cur.getFullYear()}-${pad(cur.getMonth() + 1)}-${pad(cur.getDate())}`;

        const dayNames = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
        const allEvents = (this.state.data && this.state.data.calendar_events) ? 
                          this.state.data.calendar_events.filter(e => e.type === 'task') : [];

        const days = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
            const dateIso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
            const dayEvents = allEvents.filter(e => e.date === dateIso);
            const hasOverdue = dayEvents.some(e => e.is_overdue);
            const hasCompleted = dayEvents.some(e => e.status === 'done');
            const hasInProgress = dayEvents.some(e => e.status === 'in_progress');

            days.push({
                dayName: dayNames[i],
                dayNum: d.getDate(),
                year: d.getFullYear(),
                month: d.getMonth(),
                dateIso,
                isToday: dateIso === todayIso,
                isSelected: dateIso === selectedIso,
                taskCount: dayEvents.length,
                hasOverdue,
                hasCompleted,
                hasInProgress,
                events: dayEvents,
            });
        }
        return days;
    }

    get calendarSelectedDayTasks() {
        let events = (this.state.data && this.state.data.calendar_events) ? 
                     this.state.data.calendar_events.filter(e => e.type === 'task') : [];

        // Project filter
        if (this.state.selectedProjectId) {
            events = events.filter(e => e.project_id === this.state.selectedProjectId);
        }
        // Team filter
        if (this.state.selectedTeamId) {
            if (typeof this.state.selectedTeamId === 'string' && this.state.selectedTeamId.startsWith('lead_')) {
                events = events.filter(e => e.team_id === this.state.selectedTeamId);
            } else {
                events = events.filter(e => e.team_id === this.state.selectedTeamId);
            }
        }
        // Category filter
        if (this.state.calendarCategoryFilter && this.state.calendarCategoryFilter !== 'all') {
            const cat = this.state.calendarCategoryFilter.toLowerCase();
            events = events.filter(e => (e.category || '').toLowerCase().includes(cat));
        }
        // Status filter
        if (this.state.calendarStatusFilter && this.state.calendarStatusFilter !== 'all') {
            if (this.state.calendarStatusFilter === 'overdue') {
                events = events.filter(e => e.is_overdue);
            } else if (this.state.calendarStatusFilter === 'in_progress') {
                events = events.filter(e => e.status === 'in_progress');
            } else if (this.state.calendarStatusFilter === 'under_review') {
                events = events.filter(e => e.status === 'under_review' || e.approval_state === 'submitted');
            } else if (this.state.calendarStatusFilter === 'done') {
                events = events.filter(e => e.status === 'done');
            } else if (this.state.calendarStatusFilter === 'todo') {
                events = events.filter(e => e.status === 'todo');
            }
        }
        // Search query
        if (this.state.calendarSearchQuery && this.state.calendarSearchQuery.trim()) {
            const q = this.state.calendarSearchQuery.trim().toLowerCase();
            events = events.filter(e => 
                (e.title || '').toLowerCase().includes(q) ||
                (e.code || '').toLowerCase().includes(q) ||
                (e.project_name || '').toLowerCase().includes(q) ||
                (e.responsible_name || '').toLowerCase().includes(q)
            );
        }

        // Scope filter:
        const pad = (n) => String(n).padStart(2, "0");
        const selIso = `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}-${pad(this.state.calendarDate)}`;

        if (this.state.calendarTaskFilterScope === 'day') {
            events = events.filter(e => e.date === selIso);
        } else if (this.state.calendarTaskFilterScope === 'week') {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
            const dayOfWeek = cur.getDay();
            const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
            const mon = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);
            const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
            const monIso = `${mon.getFullYear()}-${pad(mon.getMonth() + 1)}-${pad(mon.getDate())}`;
            const sunIso = `${sun.getFullYear()}-${pad(sun.getMonth() + 1)}-${pad(sun.getDate())}`;
            events = events.filter(e => e.date >= monIso && e.date <= sunIso);
        } else if (this.state.calendarTaskFilterScope === 'month') {
            const ym = `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}`;
            events = events.filter(e => e.date && e.date.startsWith(ym));
        } else if (this.state.calendarTaskFilterScope === 'overdue') {
            events = events.filter(e => e.is_overdue);
        }

        return events;
    }

    get calendarScheduledCountLabel() {
        const count = this.calendarSelectedDayTasks.length;
        return `${count} scheduled`;
    }

    setCalendarTaskScope(scope) {
        this.state.calendarTaskFilterScope = scope;
    }

    onCalendarSearchChange(ev) {
        this.state.calendarSearchQuery = ev.target.value || "";
    }

    openStandardCalendarView() {
        this.actionService.doAction("project_manage.action_project_manage_scope_calendar");
    }

    createNewTaskForSelectedDate() {
        if (!this.state.data?.user_info?.is_manager) {
            if (this.notification) {
                this.notification.add(_t("Only Project Managers can create new scopes or schedule tasks."), {
                    type: "warning",
                });
            }
            return;
        }
        const selIso = this.calendarSelectedDateIso;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_start_date: selIso,
                default_end_date: selIso,
                default_category: this.state.calendarCategoryFilter === 'implementation' ? 'Implementation' : 'Documentation',
            },
        }, {
            onClose: () => {
                this.loadData();
            }
        });
    }

    openCalendarItem(item, ev) {
        if (ev) ev.stopPropagation();
        if (item.type === 'project' && item.record_id) {
            this.openProjectScopesTab(item.record_id, ev);
        } else if (item.type === 'task' && item.record_id) {
            this.openScope(item.record_id);
        }
    }

    get calendarPeriodTitle() {
        const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const curIso = `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}-${pad(this.state.calendarDate)}`;
        const tom = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        const tomIso = `${tom.getFullYear()}-${pad(tom.getMonth() + 1)}-${pad(tom.getDate())}`;

        if (this.state.calendarTimeFilter === 'today' || (this.state.calendarViewMode === 'agenda' && curIso === todayIso)) {
            return `Today · ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
        }
        if (this.state.calendarTimeFilter === 'tomorrow' || (this.state.calendarViewMode === 'agenda' && curIso === tomIso)) {
            return `Tomorrow · ${tom.getDate()} ${months[tom.getMonth()]} ${tom.getFullYear()}`;
        }
        if (this.state.calendarViewMode === 'week' || this.state.calendarTimeFilter === 'week') {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
            const dayOfWeek = cur.getDay();
            const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
            const mon = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);
            const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
            return `Week · ${mon.getDate()} ${months[mon.getMonth()].slice(0, 3)} – ${sun.getDate()} ${months[sun.getMonth()].slice(0, 3)} ${sun.getFullYear()}`;
        }
        if (this.state.calendarTimeFilter === 'all') {
            return "All Scheduled Tasks";
        }
        return `${months[this.state.calendarMonth]} ${this.state.calendarYear}`;
    }

    get filteredCalendarEvents() {
        let events = this.state.data.calendar_events || [];

        // Strictly show tasks only
        events = events.filter(e => e.type === 'task');

        // 1. Team filter
        if (this.state.selectedTeamId) {
            events = events.filter(e => e.team_id === this.state.selectedTeamId);
        }

        // 2. Category filter (All / Documentation / Implementation)
        if (this.state.calendarCategoryFilter && this.state.calendarCategoryFilter !== 'all') {
            const cat = this.state.calendarCategoryFilter.toLowerCase();
            events = events.filter(e => (e.category || '').toLowerCase().includes(cat));
        }

        // 3. Status filter
        if (this.state.calendarStatusFilter === 'overdue') {
            events = events.filter(e => e.is_overdue);
        } else if (this.state.calendarStatusFilter === 'in_progress') {
            events = events.filter(e => e.status === 'in_progress');
        } else if (this.state.calendarStatusFilter === 'under_review') {
            events = events.filter(e => e.status === 'under_review' || e.approval_state === 'submitted');
        } else if (this.state.calendarStatusFilter === 'done') {
            events = events.filter(e => e.status === 'done');
        }

        // 4. Time filter (Today, Tomorrow, Week, Month, All)
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const tom = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        const tomIso = `${tom.getFullYear()}-${pad(tom.getMonth() + 1)}-${pad(tom.getDate())}`;

        if (this.state.calendarTimeFilter === 'today') {
            events = events.filter(e => e.date === todayIso);
        } else if (this.state.calendarTimeFilter === 'tomorrow') {
            events = events.filter(e => e.date === tomIso);
        } else if (this.state.calendarTimeFilter === 'week' || this.state.calendarViewMode === 'week') {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
            const dayOfWeek = cur.getDay();
            const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
            const mon = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);
            const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
            const monIso = `${mon.getFullYear()}-${pad(mon.getMonth() + 1)}-${pad(mon.getDate())}`;
            const sunIso = `${sun.getFullYear()}-${pad(sun.getMonth() + 1)}-${pad(sun.getDate())}`;
            events = events.filter(e => e.date >= monIso && e.date <= sunIso);
        } else if (this.state.calendarTimeFilter === 'month') {
            const ymPrefix = `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}`;
            events = events.filter(e => e.date && e.date.startsWith(ymPrefix));
        }

        return events;
    }

    get calendarStats() {
        const events = this.filteredCalendarEvents;
        return {
            total: events.length,
            documentation: events.filter(e => (e.category || '').toLowerCase().includes('doc')).length,
            implementation: events.filter(e => (e.category || '').toLowerCase().includes('impl')).length,
            in_progress: events.filter(e => e.status === 'in_progress').length,
            under_review: events.filter(e => e.status === 'under_review' || e.approval_state === 'submitted').length,
            overdue: events.filter(e => e.is_overdue).length,
            completed: events.filter(e => e.status === 'done').length,
        };
    }

    get calendarMonthGrid() {
        const year = this.state.calendarYear;
        const month = this.state.calendarMonth;
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

        const firstDay = new Date(year, month, 1);
        const dayOfWeek = firstDay.getDay(); // 0 is Sun, 1 is Mon...
        const paddingDays = dayOfWeek === 0 ? 6 : dayOfWeek - 1;
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const prevMonthLastDate = new Date(year, month, 0).getDate();

        const allEvents = this.filteredCalendarEvents;
        const cells = [];

        // Previous month padding days
        for (let i = paddingDays - 1; i >= 0; i--) {
            const d = prevMonthLastDate - i;
            const prevM = month === 0 ? 11 : month - 1;
            const prevY = month === 0 ? year - 1 : year;
            const dateIso = `${prevY}-${pad(prevM + 1)}-${pad(d)}`;
            const cellEvents = allEvents.filter(e => e.date === dateIso);
            cells.push({
                key: `prev_${d}`,
                dayNum: d,
                dateIso,
                isCurrentMonth: false,
                isToday: dateIso === todayIso,
                events: cellEvents,
                visibleEvents: cellEvents.slice(0, 3),
                moreCount: Math.max(0, cellEvents.length - 3),
            });
        }

        // Current month days
        for (let d = 1; d <= daysInMonth; d++) {
            const dateIso = `${year}-${pad(month + 1)}-${pad(d)}`;
            const cellEvents = allEvents.filter(e => e.date === dateIso);
            cells.push({
                key: `cur_${d}`,
                dayNum: d,
                dateIso,
                isCurrentMonth: true,
                isToday: dateIso === todayIso,
                events: cellEvents,
                visibleEvents: cellEvents.slice(0, 3),
                moreCount: Math.max(0, cellEvents.length - 3),
            });
        }

        // Next month trailing days to complete 35 or 42 cells
        const totalCells = cells.length <= 35 ? 35 : 42;
        const remaining = totalCells - cells.length;
        const nextM = month === 11 ? 0 : month + 1;
        const nextY = month === 11 ? year + 1 : year;

        for (let d = 1; d <= remaining; d++) {
            const dateIso = `${nextY}-${pad(nextM + 1)}-${pad(d)}`;
            const cellEvents = allEvents.filter(e => e.date === dateIso);
            cells.push({
                key: `next_${d}`,
                dayNum: d,
                dateIso,
                isCurrentMonth: false,
                isToday: dateIso === todayIso,
                events: cellEvents,
                visibleEvents: cellEvents.slice(0, 3),
                moreCount: Math.max(0, cellEvents.length - 3),
            });
        }

        return cells;
    }

    get calendarWeekDays() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayOfWeek = cur.getDay();
        const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
        const monday = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);

        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const days = [];
        const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const allEvents = this.filteredCalendarEvents;

        for (let i = 0; i < 7; i++) {
            const dayDate = new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i);
            const dateIso = `${dayDate.getFullYear()}-${pad(dayDate.getMonth() + 1)}-${pad(dayDate.getDate())}`;
            const cellEvents = allEvents.filter(e => e.date === dateIso);
            days.push({
                dayName: dayNames[i],
                dayNum: dayDate.getDate(),
                dateStr: `${dayDate.getDate()} ${months[dayDate.getMonth()]}`,
                dateIso,
                isToday: dateIso === todayIso,
                events: cellEvents,
            });
        }

        return days;
    }

    get calendarAgendaDays() {
        const events = this.filteredCalendarEvents;
        const groups = {};
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const tom = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        const tomIso = `${tom.getFullYear()}-${pad(tom.getMonth() + 1)}-${pad(tom.getDate())}`;

        for (const e of events) {
            const dStr = e.date || todayIso;
            if (!groups[dStr]) {
                const parts = dStr.split("-").map(Number);
                const dObj = new Date(parts[0], parts[1] - 1, parts[2]);
                let label = `${days[dObj.getDay()]}, ${dObj.getDate()} ${months[dObj.getMonth()]} ${dObj.getFullYear()}`;
                if (dStr === todayIso) {
                    label = `Today · ${label}`;
                } else if (dStr === tomIso) {
                    label = `Tomorrow · ${label}`;
                }
                groups[dStr] = {
                    dateIso: dStr,
                    label,
                    isToday: dStr === todayIso,
                    events: [],
                };
            }
            groups[dStr].events.push(e);
        }

        return Object.values(groups).sort((a, b) => a.dateIso.localeCompare(b.dateIso));
    }

    openScopeForm(scopeId, ev) {
        if (ev) ev.stopPropagation();
        if (!scopeId) return;
        const numericId = parseInt(scopeId, 10);
        if (isNaN(numericId) || numericId <= 0) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope",
            res_id: numericId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    startInlineEdit(item, ev) {
        if (ev) ev.stopPropagation();
        this.state.editingScopeId = item.id;
        this.state.editRowData = {
            id: item.id,
            scope: item.scope || item.scope_name || '',
            category: item.category || 'Documentation',
            name: item.name || '',
            item_type: item.item_type || '',
            responsible_id: item.responsible_id ? String(item.responsible_id) : '',
            end_date: item.end_date || '',
            state: item.state || 'todo',
        };
    }

    cancelInlineEdit(ev) {
        if (ev) ev.stopPropagation();
        this.state.editingScopeId = null;
        this.state.editRowData = {};
    }

    async saveInlineEdit(scopeId, ev) {
        if (ev) ev.stopPropagation();
        if (!scopeId || this.state.savingScope) return;
        this.state.savingScope = true;
        try {
            const vals = {
                scope: this.state.editRowData.scope,
                category: this.state.editRowData.category,
                name: this.state.editRowData.name,
                responsible_id: this.state.editRowData.responsible_id,
                end_date: this.state.editRowData.end_date,
                state: this.state.editRowData.state,
            };
            const updated = await this.orm.call("project.manage", "save_scope_inline", [scopeId, vals]);
            if (updated && !updated.error) {
                this.state.projectScopesData = updated;
                this.state.editingScopeId = null;
                this.state.editRowData = {};
                if (this.notification) {
                    this.notification.add("Task updated successfully!", { type: "success" });
                }
            } else if (updated && updated.error) {
                if (this.notification) {
                    this.notification.add(updated.error, { type: "danger" });
                }
            }
        } catch (err) {
            console.error("Failed to save scope inline:", err);
            if (this.notification) {
                this.notification.add("Failed to save changes.", { type: "danger" });
            }
        } finally {
            this.state.savingScope = false;
        }
    }

    onInlineKeydown(scopeId, ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.saveInlineEdit(scopeId, ev);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.cancelInlineEdit(ev);
        }
    }

    openScopeWizard(item = null, ev) {
        if (ev) ev.stopPropagation();
        if (!item && !this.state.data?.user_info?.is_manager) {
            if (this.notification) {
                this.notification.add(_t("Only Project Managers can create new scopes or tasks."), {
                    type: "warning",
                });
            }
            return;
        }
        if (item) {
            let respIds = [];
            if (Array.isArray(item.responsible_ids) && item.responsible_ids.length > 0) {
                respIds = item.responsible_ids.map(id => Number(id));
            } else if (item.responsible_id) {
                respIds = [Number(item.responsible_id)];
            }
            this.state.wizardData = {
                id: item.id,
                scope: item.scope || item.scope_name || '',
                category: item.category || 'Documentation',
                name: item.name || '',
                item_type: item.item_type || '',
                priority: item.priority ? String(item.priority) : '0',
                responsible_ids: respIds,
                responsible_id: respIds[0] ? String(respIds[0]) : (item.responsible_id ? String(item.responsible_id) : ''),
                start_date: item.start_date || '',
                end_date: item.end_date || '',
                state: item.state || 'todo',
            };
        } else {
            const defaultScope = this.state.selectedScopeName || (this.state.projectScopesData && this.state.projectScopesData.available_scopes && this.state.projectScopesData.available_scopes[0]) || 'Scope 0 Project Initiation & Governance';
            this.state.wizardData = {
                id: null,
                scope: defaultScope,
                category: this.state.activeCategoryFilter === 'implementation' ? 'Implementation' : 'Documentation',
                name: '',
                item_type: '',
                priority: '0',
                responsible_ids: [],
                responsible_id: '',
                start_date: '',
                end_date: '',
                state: 'todo',
            };
        }
        this.state.scopeWizardOpen = true;
    }

    getEmployeeName(empId) {
        if (!empId) return '';
        const idNum = Number(empId);
        const emps = (this.state.projectScopesData && this.state.projectScopesData.available_employees) || [];
        const found = emps.find(e => e.id === idNum);
        return found ? found.name : `Employee #${idNum}`;
    }

    isEmpSelectedInWizard(empId) {
        const idNum = Number(empId);
        const curIds = this.state.wizardData.responsible_ids || [];
        return curIds.includes(idNum);
    }

    onAddWizardResponsible(ev) {
        const val = ev.target.value;
        if (!val) return;
        const idNum = Number(val);
        if (!Array.isArray(this.state.wizardData.responsible_ids)) {
            this.state.wizardData.responsible_ids = [];
        }
        if (!this.state.wizardData.responsible_ids.includes(idNum)) {
            this.state.wizardData.responsible_ids.push(idNum);
            this.state.wizardData.responsible_id = String(this.state.wizardData.responsible_ids[0]);
        }
        ev.target.value = "";
    }

    removeWizardResponsible(empId) {
        const idNum = Number(empId);
        if (Array.isArray(this.state.wizardData.responsible_ids)) {
            this.state.wizardData.responsible_ids = this.state.wizardData.responsible_ids.filter(id => id !== idNum);
            this.state.wizardData.responsible_id = this.state.wizardData.responsible_ids[0] ? String(this.state.wizardData.responsible_ids[0]) : '';
        }
    }

    toggleWizardResponsible(empId) {
        const idNum = Number(empId);
        if (!Array.isArray(this.state.wizardData.responsible_ids)) {
            this.state.wizardData.responsible_ids = [];
        }
        if (this.state.wizardData.responsible_ids.includes(idNum)) {
            this.removeWizardResponsible(idNum);
        } else {
            this.state.wizardData.responsible_ids.push(idNum);
            this.state.wizardData.responsible_id = String(this.state.wizardData.responsible_ids[0]);
        }
    }

    clearWizardResponsible() {
        this.state.wizardData.responsible_ids = [];
        this.state.wizardData.responsible_id = '';
    }

    isStarActive(priority, star) {
        return (Number(priority) || 0) >= star;
    }

    setWizardPriority(star) {
        const cur = parseInt(this.state.wizardData.priority || '0');
        if (cur === star) {
            this.state.wizardData.priority = '0';
        } else {
            this.state.wizardData.priority = String(star);
        }
    }

    async toggleScopePriority(item, star, ev) {
        if (ev) ev.stopPropagation();
        const cur = parseInt(item.priority || '0');
        const nextVal = (cur === star) ? '0' : String(star);
        item.priority = nextVal;
        try {
            await this.orm.call("project.manage", "save_scope_inline", [item.id, { priority: nextVal }]);
            if (this.notification) {
                const labels = { '0': 'Normal', '1': 'Low (1 Star)', '2': 'High (2 Stars)', '3': 'Very High (3 Stars)' };
                this.notification.add(`Priority set to ${labels[nextVal]}`, { type: "info" });
            }
        } catch (err) {
            console.error("Failed to update priority inline:", err);
        }
    }

    closeScopeWizard() {
        this.state.scopeWizardOpen = false;
        this.state.wizardData = {};
    }

    async saveScopeWizard(andNext = false) {
        if (this.state.savingScope) return;
        if (!this.state.wizardData.name || !this.state.wizardData.name.trim()) {
            if (this.notification) {
                this.notification.add("Task / Document Name is required.", { type: "warning" });
            }
            return;
        }

        this.state.savingScope = true;
        try {
            const respIds = Array.isArray(this.state.wizardData.responsible_ids) ? this.state.wizardData.responsible_ids : [];
            const primaryRespId = respIds.length > 0 ? respIds[0] : (this.state.wizardData.responsible_id || false);
            const vals = {
                scope: this.state.wizardData.scope,
                category: this.state.wizardData.category,
                name: this.state.wizardData.name,
                item_type: this.state.wizardData.item_type,
                priority: this.state.wizardData.priority || '0',
                responsible_ids: respIds,
                responsible_id: primaryRespId,
                start_date: this.state.wizardData.start_date,
                end_date: this.state.wizardData.end_date,
                state: this.state.wizardData.state,
            };

            let updated = null;
            if (this.state.wizardData.id) {
                updated = await this.orm.call("project.manage", "save_scope_inline", [this.state.wizardData.id, vals]);
            } else {
                const projectId = this.state.projectScopesData.project.id;
                updated = await this.orm.call("project.manage", "create_scope_from_dashboard", [projectId, vals]);
            }

            if (updated && !updated.error) {
                this.state.projectScopesData = updated;
                if (this.notification) {
                    const msg = updated.message || (this.state.wizardData.id ? "Scope task saved!" : "New scope task created!");
                    this.notification.add(msg, { type: "success" });
                }

                if (andNext && this.state.wizardData.id) {
                    const curId = this.state.wizardData.id;
                    const scopes = this.filteredScopes;
                    const idx = scopes.findIndex(s => s.id === curId);
                    if (idx !== -1 && idx < scopes.length - 1) {
                        const nextItem = scopes[idx + 1];
                        this.openScopeWizard(nextItem);
                        return;
                    }
                }
                this.closeScopeWizard();
            } else if (updated && updated.error) {
                if (this.notification) {
                    this.notification.add(updated.error, { type: "danger" });
                }
            }
        } catch (err) {
            console.error("Failed to save wizard data:", err);
            if (this.notification) {
                this.notification.add("Error saving scope.", { type: "danger" });
            }
        } finally {
            this.state.savingScope = false;
        }
    }

    openBulkFillWizard(ev) {
        if (ev) ev.stopPropagation();
        const defaultScope = this.state.selectedScopeName || (this.state.projectScopesData && this.state.projectScopesData.available_scopes && this.state.projectScopesData.available_scopes[0]) || '';
        this.state.bulkData = {
            target: defaultScope ? 'scope' : 'all',
            scope_name_filter: defaultScope,
            responsible_id: '',
            responsible_ids: [],
            start_date: '',
            end_date: '',
            state: '',
            category: '',
        };
        this.state.bulkWizardOpen = true;
    }

    closeBulkFillWizard() {
        this.state.bulkWizardOpen = false;
    }

    onAddBulkResponsible(ev) {
        const val = ev.target.value;
        if (!val) return;
        const idNum = Number(val);
        if (!Array.isArray(this.state.bulkData.responsible_ids)) {
            this.state.bulkData.responsible_ids = [];
        }
        if (!this.state.bulkData.responsible_ids.includes(idNum)) {
            this.state.bulkData.responsible_ids.push(idNum);
            this.state.bulkData.responsible_id = String(this.state.bulkData.responsible_ids[0]);
        }
        ev.target.value = "";
    }

    removeBulkResponsible(empId) {
        const idNum = Number(empId);
        if (Array.isArray(this.state.bulkData.responsible_ids)) {
            this.state.bulkData.responsible_ids = this.state.bulkData.responsible_ids.filter(id => id !== idNum);
            this.state.bulkData.responsible_id = this.state.bulkData.responsible_ids[0] ? String(this.state.bulkData.responsible_ids[0]) : '';
        }
    }

    toggleBulkResponsible(empId) {
        const idNum = Number(empId);
        if (!Array.isArray(this.state.bulkData.responsible_ids)) {
            this.state.bulkData.responsible_ids = [];
        }
        if (this.state.bulkData.responsible_ids.includes(idNum)) {
            this.removeBulkResponsible(idNum);
        } else {
            this.state.bulkData.responsible_ids.push(idNum);
            this.state.bulkData.responsible_id = String(this.state.bulkData.responsible_ids[0]);
        }
    }

    clearBulkResponsible() {
        this.state.bulkData.responsible_ids = [];
        this.state.bulkData.responsible_id = '';
    }

    async applyBulkFill() {
        if (this.state.savingScope) return;
        const projectId = this.state.projectScopesData.project.id;
        const vals = {};
        if (this.state.bulkData.target === 'scope' && this.state.bulkData.scope_name_filter) {
            vals.scope_name_filter = this.state.bulkData.scope_name_filter;
        }
        if (Array.isArray(this.state.bulkData.responsible_ids) && this.state.bulkData.responsible_ids.length > 0) {
            vals.responsible_ids = this.state.bulkData.responsible_ids;
            vals.responsible_id = this.state.bulkData.responsible_ids[0];
        } else if (this.state.bulkData.responsible_id) {
            vals.responsible_id = this.state.bulkData.responsible_id;
            vals.responsible_ids = [Number(this.state.bulkData.responsible_id)];
        }
        if (this.state.bulkData.start_date) {
            vals.start_date = this.state.bulkData.start_date;
        }
        if (this.state.bulkData.end_date) {
            vals.end_date = this.state.bulkData.end_date;
        }
        if (this.state.bulkData.state) {
            vals.state = this.state.bulkData.state;
        }
        if (this.state.bulkData.category) {
            vals.category = this.state.bulkData.category;
        }

        const hasResponsible = (Array.isArray(this.state.bulkData.responsible_ids) && this.state.bulkData.responsible_ids.length > 0) || Boolean(this.state.bulkData.responsible_id);
        if (!hasResponsible && !vals.start_date && !vals.end_date && !vals.state && !vals.category) {
            if (this.notification) {
                this.notification.add("Please select at least one field to update (Responsible, Start Date, End Date, Status, or Category).", { type: "warning" });
            }
            return;
        }

        this.state.savingScope = true;
        try {
            const updated = await this.orm.call("project.manage", "bulk_fill_scopes", [projectId, null, vals]);
            if (updated && !updated.error) {
                this.state.projectScopesData = updated;
                this.closeBulkFillWizard();
                if (this.notification) {
                    this.notification.add("Bulk fill applied successfully!", { type: "success" });
                }
            } else if (updated && updated.error) {
                if (this.notification) {
                    this.notification.add(updated.error, { type: "danger" });
                }
            }
        } catch (err) {
            console.error("Failed to apply bulk fill:", err);
            if (this.notification) {
                this.notification.add("Failed to apply bulk fill.", { type: "danger" });
            }
        } finally {
            this.state.savingScope = false;
        }
    }

    openImportWizardForProject(projectId, ev) {
        if (ev) ev.stopPropagation();
        if (!this.state.data?.user_info?.is_manager) {
            if (this.notification) {
                this.notification.add(_t("Only Project Managers can import or create scopes."), {
                    type: "warning",
                });
            }
            return;
        }
        const numericId = parseInt(projectId, 10);
        if (isNaN(numericId) || numericId <= 0) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.scope.import.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { default_project_id: numericId },
        }, {
            onClose: async () => {
                const targetId = this.state.selectedProjectId || numericId;
                if (targetId) {
                    this.state.selectedProjectId = targetId;
                    await this.loadProjectScopes(targetId);
                }
                await this.loadData();
            }
        });
    }

    async syncProjectImportedScopes(projectId, ev) {
        if (ev) ev.stopPropagation();
        try {
            await this.orm.call('project.manage', 'action_sync_imported_scopes', [[projectId]]);
            if (this.notification) {
                this.notification.add("Imported tasks synced into project successfully.", { type: "success" });
            }
            await this.loadProjectScopes(projectId);
            await this.loadData();
        } catch (err) {
            console.error("Failed to sync imported scopes:", err);
            if (this.notification) {
                this.notification.add("Failed to sync imported tasks.", { type: "danger" });
            }
        }
    }

    async openClientUpdateWizard(projectId, ev) {
        if (ev) ev.stopPropagation();
        if (!projectId) return;
        try {
            const action = await this.orm.call("project.manage", "action_open_client_update_wizard", [projectId]);
            if (action) {
                if (!action.views || !Array.isArray(action.views)) {
                    action.views = [[false, "form"]];
                }
                this.actionService.doAction(action);
            }
        } catch (err) {
            console.error("Failed to open client update wizard:", err);
            if (this.notification) {
                this.notification.add("Could not open client update wizard: " + (err.data && err.data.message || err.message), { type: "danger" });
            }
        }
    }

    openCustomerReviews(projectId, ev) {
        if (ev) ev.stopPropagation();
        this.actionService.doAction({
            name: "Customer Reviews",
            type: "ir.actions.act_window",
            res_model: "project.manage.review",
            view_mode: "list,kanban,form,pivot,graph",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
                [false, "pivot"],
                [false, "graph"],
            ],
            domain: projectId ? [["project_id", "=", projectId]] : [],
            context: projectId ? { default_project_id: projectId } : {},
        });
    }

    async startScopeDashboard(scopeId, ev) {
        if (ev) ev.stopPropagation();
        try {
            await this.orm.call("project.manage", "action_dashboard_start_scope", [], { scope_id: scopeId });
            if (this.notification) {
                this.notification.add("Task started and marked In Progress", { type: "success" });
            }
            if (this.state.selectedProjectId) {
                await this.loadProjectScopes(this.state.selectedProjectId);
            }
            await this.loadData();
        } catch (err) {
            console.error("Failed to start task:", err);
            if (this.notification) {
                this.notification.add("Could not start task.", { type: "danger" });
            }
        }
    }

    async submitScopeDashboard(scopeId, ev) {
        if (ev) ev.stopPropagation();
        try {
            await this.orm.call("project.manage", "action_dashboard_submit_scope", [], { scope_id: scopeId });
            if (this.notification) {
                this.notification.add("Task marked complete and submitted for review", { type: "success" });
            }
            if (this.state.selectedProjectId) {
                await this.loadProjectScopes(this.state.selectedProjectId);
            }
            await this.loadData();
        } catch (err) {
            console.error("Failed to submit task:", err);
            if (this.notification) {
                this.notification.add("Could not submit task.", { type: "danger" });
            }
        }
    }

    async approveScopeDashboard(scopeId, ev) {
        if (ev) ev.stopPropagation();
        try {
            await this.orm.call("project.manage", "action_dashboard_approve_scope", [], { scope_id: scopeId });
            if (this.notification) {
                this.notification.add("Task approved and forwarded to next tier", { type: "success" });
            }
            if (this.state.selectedProjectId) {
                await this.loadProjectScopes(this.state.selectedProjectId);
            }
            await this.loadData();
        } catch (err) {
            console.error("Failed to approve task:", err);
            if (this.notification) {
                this.notification.add("Could not approve task.", { type: "danger" });
            }
        }
    }

    async rejectScopeDashboard(scopeId, ev) {
        if (ev) ev.stopPropagation();
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope.reject.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { default_scope_id: scopeId },
        }, {
            onClose: async () => {
                if (this.state.selectedProjectId) {
                    await this.loadProjectScopes(this.state.selectedProjectId);
                }
                await this.loadData();
            }
        });
    }

    openProject(projectId) {
        if (!projectId) return;
        const numericId = parseInt(projectId, 10);
        if (isNaN(numericId) || numericId <= 0) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage",
            res_id: numericId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTeam(teamId) {
        if (!teamId) return;
        if (typeof teamId === "string" && teamId.startsWith("lead_")) {
            const leadId = parseInt(teamId.replace("lead_", ""), 10);
            if (!isNaN(leadId) && leadId > 0) {
                this.actionService.doAction({
                    name: "Team Projects",
                    type: "ir.actions.act_window",
                    res_model: "project.manage",
                    views: [[false, "list"], [false, "kanban"], [false, "form"]],
                    domain: [["team_lead_id", "=", leadId]],
                    context: { default_team_lead_id: leadId },
                    target: "current",
                });
            }
            return;
        }
        const numericId = parseInt(teamId, 10);
        if (isNaN(numericId) || numericId <= 0) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.team",
            res_id: numericId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async createNewProject() {
        if (!this.state.data.user_info.can_create_project) {
            if (this.notification) {
                this.notification.add("Team Leads cannot create projects. Only Project Managers, VP, CEO, and Administrators have project creation access.", { type: "warning" });
            }
            return;
        }
        this.state.projectWizardOpen = true;
        this.state.projectWizardLoading = true;
        try {
            if (!this.state.projectFormData) {
                const meta = await this.orm.call("project.manage", "get_new_project_form_data", []);
                this.state.projectFormData = meta || {};
            }
            const meta = this.state.projectFormData;
            const todayStr = meta.default_date_start || new Date().toISOString().split('T')[0];
            const endStr = meta.default_date_end || todayStr;
            this.state.newProjectData = {
                name: "",
                priority: "0",
                partner_id: "",
                client_coordinator_id: "",
                date_start: todayStr,
                date_end: endStr,
                tag_ids: [],
                team_id: "",
                manager_id: meta.default_manager_id || (meta.employees && meta.employees[0] ? meta.employees[0].id : ""),
                team_lead_id: "",
                project_coordinator_id: "",
                consultant_ids: [],
                load_standard_scopes: true,
                import_file: null,
                import_filename: "",
            };
        } catch (err) {
            console.error("Failed to load project form data:", err);
            if (this.notification) {
                this.notification.add("Could not load project setup form.", { type: "danger" });
            }
        } finally {
            this.state.projectWizardLoading = false;
        }
    }

    closeProjectWizard() {
        if (this.state.savingNewProject) {
            return;
        }
        this.state.projectWizardOpen = false;
    }

    isProjectStarActive(star) {
        const cur = parseInt(this.state.newProjectData.priority || 0, 10);
        return cur >= star;
    }

    setNewProjectPriority(star) {
        const starStr = String(star);
        this.state.newProjectData.priority = (this.state.newProjectData.priority === starStr) ? "0" : starStr;
    }

    onProjectTeamSelect(ev) {
        const teamIdVal = ev.target.value;
        this.state.newProjectData.team_id = teamIdVal;
        if (!teamIdVal || !this.state.projectFormData || !this.state.projectFormData.teams) {
            return;
        }
        const selectedTeam = this.state.projectFormData.teams.find(t => String(t.id) === String(teamIdVal));
        if (selectedTeam) {
            if (selectedTeam.team_lead_emp_id) {
                this.state.newProjectData.team_lead_id = selectedTeam.team_lead_emp_id;
            }
            if (selectedTeam.member_emp_ids && selectedTeam.member_emp_ids.length > 0) {
                const current = new Set(this.state.newProjectData.consultant_ids);
                selectedTeam.member_emp_ids.forEach(id => current.add(id));
                this.state.newProjectData.consultant_ids = Array.from(current);
            }
        }
    }

    onProjectClientSelect(ev) {
        const partnerId = ev.target.value;
        this.state.newProjectData.partner_id = partnerId;
        if (partnerId && !this.state.newProjectData.client_coordinator_id) {
            this.state.newProjectData.client_coordinator_id = partnerId;
        }
    }

    getFilteredCoordinators() {
        if (!this.state.projectFormData || !this.state.projectFormData.coordinators) {
            return [];
        }
        return this.state.projectFormData.coordinators;
    }

    getEmployeeNameFromMeta(empId) {
        if (!empId) return "";
        if (this.state.projectFormData && this.state.projectFormData.employees) {
            const found = this.state.projectFormData.employees.find(e => e.id === empId);
            if (found) return found.name;
        }
        return this.getEmployeeName(empId);
    }

    addProjectConsultant(ev) {
        const empId = parseInt(ev.target.value, 10);
        if (!empId) return;
        if (!this.state.newProjectData.consultant_ids.includes(empId)) {
            this.state.newProjectData.consultant_ids.push(empId);
        }
        ev.target.value = "";
    }

    removeProjectConsultant(empId) {
        this.state.newProjectData.consultant_ids = this.state.newProjectData.consultant_ids.filter(id => id !== empId);
    }

    toggleProjectTag(tagId) {
        const current = this.state.newProjectData.tag_ids;
        if (current.includes(tagId)) {
            this.state.newProjectData.tag_ids = current.filter(id => id !== tagId);
        } else {
            this.state.newProjectData.tag_ids.push(tagId);
        }
    }

    onProjectImportFileChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.newProjectData.import_file = e.target.result;
            this.state.newProjectData.import_filename = file.name;
            this.state.newProjectData.load_standard_scopes = false;
        };
        reader.readAsDataURL(file);
    }

    clearProjectImportFile() {
        this.state.newProjectData.import_file = null;
        this.state.newProjectData.import_filename = "";
        this.state.newProjectData.load_standard_scopes = true;
    }

    async downloadScopeTemplate() {
        try {
            const res = await this.orm.call("project.manage", "get_default_scope_csv_template", []);
            if (res && res.file_content) {
                const link = document.createElement("a");
                link.href = "data:text/csv;base64," + res.file_content;
                link.download = res.filename || "project_scope_template.csv";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
        } catch (err) {
            console.error("Failed to download template:", err);
            if (this.notification) {
                this.notification.add("Could not download template file.", { type: "danger" });
            }
        }
    }

    async saveNewProject() {
        const data = this.state.newProjectData;
        if (!data.name || !data.name.trim()) {
            if (this.notification) this.notification.add("Project Name is required.", { type: "warning" });
            return;
        }
        if (!data.partner_id) {
            if (this.notification) this.notification.add("Please select a Client.", { type: "warning" });
            return;
        }
        if (!data.date_start || !data.date_end) {
            if (this.notification) this.notification.add("Please provide Start and End Dates.", { type: "warning" });
            return;
        }
        if (new Date(data.date_end) < new Date(data.date_start)) {
            if (this.notification) this.notification.add("End date cannot be earlier than start date.", { type: "warning" });
            return;
        }
        if (!data.manager_id) {
            if (this.notification) this.notification.add("Please select a Project Manager.", { type: "warning" });
            return;
        }
        if (!data.team_lead_id) {
            if (this.notification) this.notification.add("Please select a Team Lead.", { type: "warning" });
            return;
        }
        if (!data.consultant_ids || data.consultant_ids.length === 0) {
            data.consultant_ids = [parseInt(data.team_lead_id, 10)];
        }

        this.state.savingNewProject = true;
        try {
            const res = await this.orm.call("project.manage", "create_project_from_dashboard", [data]);
            if (res && res.success) {
                if (this.notification) {
                    this.notification.add(`Project "${res.project_name}" created successfully!`, { type: "success" });
                }
                this.state.projectWizardOpen = false;
                this.state.selectedProjectId = res.project_id;
                await this.loadData();
                await this.loadProjectScopes(res.project_id);
            }
        } catch (err) {
            console.error("Failed to create project from dashboard:", err);
            const msg = err && err.data && err.data.message ? err.data.message : (err && err.message ? err.message : "Failed to create project.");
            if (this.notification) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this.state.savingNewProject = false;
        }
    }

    async openEditProjectWizard(projectId, ev) {
        if (ev) ev.stopPropagation();
        if (!projectId) return;
        const numericId = parseInt(projectId, 10);
        if (isNaN(numericId) || numericId <= 0) return;

        if (this.state.projectDetailWizardOpen) {
            this.state.projectDetailWizardOpen = false;
        }

        this.state.editProjectWizardOpen = true;
        this.state.editProjectWizardLoading = true;
        try {
            const res = await this.orm.call("project.manage", "get_project_for_edit", [numericId]);
            if (res && res.project) {
                if (res.meta) {
                    this.state.projectFormData = res.meta;
                }
                const p = res.project;
                this.state.editProjectData = {
                    id: p.id,
                    name: p.name || "",
                    priority: String(p.priority || "0"),
                    partner_id: p.partner_id ? String(p.partner_id) : "",
                    client_coordinator_id: p.client_coordinator_id ? String(p.client_coordinator_id) : "",
                    date_start: p.date_start || "",
                    date_end: p.date_end || "",
                    tag_ids: Array.isArray(p.tag_ids) ? [...p.tag_ids] : [],
                    team_id: p.team_id ? String(p.team_id) : "",
                    manager_id: p.manager_id ? String(p.manager_id) : "",
                    team_lead_id: p.team_lead_id ? String(p.team_lead_id) : "",
                    project_coordinator_id: p.project_coordinator_id ? String(p.project_coordinator_id) : "",
                    consultant_ids: Array.isArray(p.consultant_ids) ? [...p.consultant_ids] : [],
                    state: p.state || "todo",
                    health: p.health || "good",
                    risk_level: p.risk_level || "low",
                };
            } else {
                if (this.notification) {
                    this.notification.add("Could not load project for editing.", { type: "danger" });
                }
                this.state.editProjectWizardOpen = false;
            }
        } catch (err) {
            console.error("Failed to load project for edit:", err);
            if (this.notification) {
                this.notification.add("Failed to load project details.", { type: "danger" });
            }
            this.state.editProjectWizardOpen = false;
        } finally {
            this.state.editProjectWizardLoading = false;
        }
    }

    closeEditProjectWizard() {
        if (this.state.savingEditProject) return;
        this.state.editProjectWizardOpen = false;
        this.state.editProjectData = null;
    }

    isEditProjectStarActive(star) {
        if (!this.state.editProjectData) return false;
        const cur = parseInt(this.state.editProjectData.priority || 0, 10);
        return cur >= star;
    }

    setEditProjectPriority(star) {
        if (!this.state.editProjectData) return;
        const cur = parseInt(this.state.editProjectData.priority || 0, 10);
        this.state.editProjectData.priority = (cur === star) ? "0" : String(star);
    }

    onEditProjectClientSelect(ev) {
        if (!this.state.editProjectData) return;
        const clientId = ev.target.value;
        this.state.editProjectData.partner_id = clientId;
        if (clientId && (!this.state.editProjectData.client_coordinator_id || this.state.editProjectData.client_coordinator_id === "")) {
            this.state.editProjectData.client_coordinator_id = clientId;
        }
    }

    onEditProjectTeamSelect(ev) {
        if (!this.state.editProjectData) return;
        const teamIdVal = ev.target.value;
        this.state.editProjectData.team_id = teamIdVal;
        if (!teamIdVal || !this.state.projectFormData || !this.state.projectFormData.teams) {
            return;
        }
        const selectedTeam = this.state.projectFormData.teams.find(t => String(t.id) === String(teamIdVal));
        if (selectedTeam) {
            if (selectedTeam.team_lead_emp_id) {
                this.state.editProjectData.team_lead_id = String(selectedTeam.team_lead_emp_id);
            }
            if (selectedTeam.member_emp_ids && selectedTeam.member_emp_ids.length > 0) {
                const current = new Set(this.state.editProjectData.consultant_ids || []);
                selectedTeam.member_emp_ids.forEach(id => current.add(id));
                this.state.editProjectData.consultant_ids = Array.from(current);
            }
        }
    }

    toggleEditProjectTag(tagId) {
        if (!this.state.editProjectData) return;
        const cur = this.state.editProjectData.tag_ids || [];
        if (cur.includes(tagId)) {
            this.state.editProjectData.tag_ids = cur.filter(id => id !== tagId);
        } else {
            this.state.editProjectData.tag_ids = [...cur, tagId];
        }
    }

    addEditProjectConsultant(ev) {
        if (!this.state.editProjectData) return;
        const val = ev.target.value;
        if (!val) return;
        const empId = parseInt(val, 10);
        if (isNaN(empId)) return;
        if (!this.state.editProjectData.consultant_ids.includes(empId)) {
            this.state.editProjectData.consultant_ids.push(empId);
        }
        ev.target.value = "";
    }

    removeEditProjectConsultant(empId) {
        if (!this.state.editProjectData) return;
        this.state.editProjectData.consultant_ids = (this.state.editProjectData.consultant_ids || []).filter(id => id !== empId);
    }

    async saveEditProject() {
        if (!this.state.editProjectData) return;
        const data = this.state.editProjectData;
        if (!data.name || !data.name.trim()) {
            if (this.notification) this.notification.add("Project Name is required.", { type: "warning" });
            return;
        }
        if (!data.partner_id) {
            if (this.notification) this.notification.add("Please select a Client.", { type: "warning" });
            return;
        }
        if (!data.date_start || !data.date_end) {
            if (this.notification) this.notification.add("Please provide Start and End Dates.", { type: "warning" });
            return;
        }
        if (new Date(data.date_end) < new Date(data.date_start)) {
            if (this.notification) this.notification.add("End date cannot be earlier than start date.", { type: "warning" });
            return;
        }
        if (!data.manager_id) {
            if (this.notification) this.notification.add("Please select a Project Manager.", { type: "warning" });
            return;
        }
        if (!data.team_lead_id) {
            if (this.notification) this.notification.add("Please select a Team Lead.", { type: "warning" });
            return;
        }
        if (!data.consultant_ids || data.consultant_ids.length === 0) {
            data.consultant_ids = [parseInt(data.team_lead_id, 10)];
        }

        this.state.savingEditProject = true;
        try {
            const res = await this.orm.call("project.manage", "update_project_from_dashboard", [data.id, data]);
            if (res && res.success) {
                if (this.notification) {
                    this.notification.add(`Project "${res.project_name}" updated successfully!`, { type: "success" });
                }
                const updatedId = data.id;
                this.state.editProjectWizardOpen = false;
                this.state.editProjectData = null;
                await this.loadData();
                if (this.state.selectedProjectId === updatedId) {
                    await this.loadProjectScopes(updatedId);
                }
            }
        } catch (err) {
            console.error("Failed to update project from dashboard:", err);
            const msg = err && err.data && err.data.message ? err.data.message : (err && err.message ? err.message : "Failed to update project.");
            if (this.notification) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this.state.savingEditProject = false;
        }
    }

    createNewTeam() {
        if (!this.state.data.user_info.can_see_all_teams) {
            if (this.notification) {
                this.notification.add("Team Leads cannot create new teams.", { type: "warning" });
            }
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.team",
            views: [[false, "form"]],
            target: "current",
        });
    }

    scrollToProjectsTable() {
        if (this.state.activeMainView === 'calendar') {
            this.setActiveTab('home');
        }
        if (this.state.isMobile) {
            this.setActiveTab('projects');
        } else if (typeof document !== 'undefined') {
            setTimeout(() => {
                const el = document.querySelector(".pm-table-section");
                if (el) {
                    el.scrollIntoView({ behavior: "smooth", block: "start" });
                }
            }, 60);
        }
    }

    viewAllProjects(domain = [], name = "Projects") {
        this.openProjectCardsWizard('all', '', 'Total Projects', 'All portfolio projects');
    }

    viewRunningProjects() {
        this.openProjectCardsWizard('running_status', 'running', 'Running Projects', 'Projects currently active and in progress');
    }

    viewProjectsByRunningStatus(status, ev) {
        if (ev) ev.stopPropagation();
        const labelMap = {
            running: 'Running Projects',
            completed: 'Completed Projects',
            on_hold: 'On-Hold Projects',
            not_started: 'Not Started Projects',
        };
        const title = labelMap[status] || 'Projects by Running Status';
        this.openProjectCardsWizard('running_status', status, title, '', ev);
    }

    viewHighRiskProjects() {
        this.openProjectCardsWizard('risk', 'high', 'High-Risk Projects', 'Critical projects requiring immediate attention');
    }

    viewProjectsByRisk(level, ev) {
        if (ev) ev.stopPropagation();
        const labelMap = {
            low: 'Low-Risk Projects',
            medium: 'Medium-Risk Projects',
            high: 'High-Risk Projects',
        };
        const title = labelMap[level] || 'Projects by Risk Level';
        this.openProjectCardsWizard('risk', level, title, '', ev);
    }

    viewProjectsByHealth(health, ev) {
        if (ev) ev.stopPropagation();
        const labelMap = {
            good: 'Good Health Projects',
            fair: 'Fair Health Projects',
            poor: 'Poor Health Projects',
        };
        const title = labelMap[health] || 'Projects by Health Status';
        this.openProjectCardsWizard('health', health, title, '', ev);
    }

    viewProjectsByCondition(condition, ev) {
        if (ev) ev.stopPropagation();
        const labelMap = {
            ahead: 'Ahead of Plan Projects',
            on_plan: 'On Plan Projects',
            behind: 'Behind Plan Projects',
            overdue: 'Overdue Projects',
        };
        const title = labelMap[condition] || 'Projects by Condition';
        this.openProjectCardsWizard('condition', condition, title, '', ev);
    }

    viewOnTimeProjects(ev) {
        if (ev) ev.stopPropagation();
        this.openProjectCardsWizard('on_time', '', 'On-Time Delivery Projects', 'Projects delivering ahead of or on planned schedule', ev);
    }

    filterProjectsByTeam(teamId, ev) {
        if (ev) ev.stopPropagation();
        const tm = this.state.data?.teams?.find(t => String(t.id) === String(teamId));
        const title = (tm ? tm.name : 'Team') + ' — Projects';
        this.openProjectCardsWizard('team', teamId, title, 'Projects assigned to this team', ev);
    }

    async approveTask(taskId) {
        if (!taskId) return;
        try {
            await this.orm.call("project.manage", "action_dashboard_approve_scope", [], { scope_id: taskId });
            if (this.notification) {
                this.notification.add("Task approved and forwarded to next tier", { type: "success" });
            }
            await this.loadData();
        } catch (err) {
            console.error("Failed to approve task:", err);
            if (this.notification) {
                this.notification.add("Could not approve task.", { type: "danger" });
            }
        }
    }

    openRejectWizard(taskId) {
        if (!taskId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope.reject.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { default_scope_id: taskId },
        }, {
            onClose: () => this.loadData(),
        });
    }

    async submitTask(taskId) {
        if (!taskId) return;
        try {
            await this.orm.call("project.manage", "action_dashboard_submit_scope", [], { scope_id: taskId });
            if (this.notification) {
                this.notification.add("Task marked complete and submitted for review", { type: "success" });
            }
            await this.loadData();
        } catch (err) {
            console.error("Failed to submit task:", err);
            if (this.notification) {
                this.notification.add("Could not submit task.", { type: "danger" });
            }
        }
    }

    async openScope(scopeId) {
        if (!scopeId) return;
        const numericId = parseInt(scopeId, 10);
        if (isNaN(numericId) || numericId <= 0) return;

        this.state.scopeDetailWizardOpen = true;
        this.state.scopeDetailLoading = true;
        this.state.scopeDetailData = null;
        try {
            const data = await this.orm.call("project.manage.scope", "get_scope_details_dashboard", [numericId]);
            if (data && !data.error) {
                this.state.scopeDetailData = data;
            } else {
                if (this.notification) this.notification.add(data.error || "Could not load task details.", { type: "danger" });
                this.state.scopeDetailWizardOpen = false;
            }
        } catch (err) {
            console.error("Failed to load task details:", err);
            if (this.notification) this.notification.add("Could not load task details.", { type: "danger" });
            this.state.scopeDetailWizardOpen = false;
        } finally {
            this.state.scopeDetailLoading = false;
        }
    }

    closeScopeDetailWizard() {
        this.state.scopeDetailWizardOpen = false;
        this.state.scopeDetailData = null;
    }

    async approveTaskFromModal(scopeId) {
        if (!scopeId) return;
        try {
            await this.orm.call("project.manage", "action_dashboard_approve_scope", [scopeId]);
            if (this.notification) {
                this.notification.add("Deliverable approved successfully!", { type: "success" });
            }
            this.closeScopeDetailWizard();
            await this.loadData();
            if (this.state.selectedProjectId) {
                await this.loadProjectScopes(this.state.selectedProjectId);
            }
        } catch (err) {
            console.error("Failed to approve task:", err);
            if (this.notification) this.notification.add("Failed to approve deliverable.", { type: "danger" });
        }
    }

    async rejectTaskFromModal(scopeId) {
        if (!scopeId) return;
        this.closeScopeDetailWizard();
        this.openRejectWizard(scopeId);
    }

    async onModalDocumentUpload(ev, scopeId) {
        const file = ev.target.files && ev.target.files[0];
        if (!file || !scopeId) return;
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const res = await this.orm.call("project.manage.scope", "upload_document_to_scope_dashboard", [
                    scopeId,
                    e.target.result,
                    file.name,
                    "deliverable"
                ]);
                if (res && !res.error) {
                    this.state.scopeDetailData = res;
                    if (this.notification) {
                        this.notification.add(`Document "${file.name}" uploaded successfully.`, { type: "success" });
                    }
                    await this.loadData();
                }
            } catch (err) {
                console.error("Failed to upload document:", err);
                if (this.notification) this.notification.add("Failed to upload document.", { type: "danger" });
            }
        };
        reader.readAsDataURL(file);
    }

    getFileIcon(filename) {
        if (!filename) return "fa-file-o";
        const f = filename.toLowerCase();
        if (f.endsWith(".pdf")) return "fa-file-pdf-o text-danger";
        if (f.endsWith(".xlsx") || f.endsWith(".xls") || f.endsWith(".csv")) return "fa-file-excel-o text-success";
        if (f.endsWith(".docx") || f.endsWith(".doc")) return "fa-file-word-o text-primary";
        if (f.endsWith(".png") || f.endsWith(".jpg") || f.endsWith(".jpeg") || f.endsWith(".webp")) return "fa-file-image-o text-warning";
        if (f.endsWith(".zip") || f.endsWith(".rar") || f.endsWith(".7z")) return "fa-file-archive-o text-secondary";
        return "fa-file-text-o text-info";
    }

    viewAllApprovals() {
        this.setActiveTab('approvals');
    }

    viewMyTasks() {
        this.setActiveTab('scopes');
    }

    async refresh() {
        await this.loadData();
        if (this.notification) {
            this.notification.add("Dashboard refreshed", { type: "success" });
        }
    }

    async openProjectDetailWizard(projectId) {
        if (!projectId) return;
        const numericId = parseInt(projectId, 10);
        if (isNaN(numericId) || numericId <= 0) return;

        this.state.projectDetailWizardOpen = true;
        this.state.projectDetailLoading = true;
        this.state.projectDetailData = null;
        try {
            const data = await this.orm.call("project.manage", "get_project_detail_dashboard", [numericId]);
            if (data && !data.error) {
                this.state.projectDetailData = data;
            } else {
                if (this.notification) this.notification.add((data && data.error) || "Could not load project details.", { type: "danger" });
                this.state.projectDetailWizardOpen = false;
            }
        } catch (err) {
            console.error("Failed to load project details:", err);
            if (this.notification) this.notification.add("Could not load project details.", { type: "danger" });
            this.state.projectDetailWizardOpen = false;
        } finally {
            this.state.projectDetailLoading = false;
        }
    }

    closeProjectDetailWizard() {
        this.state.projectDetailWizardOpen = false;
        this.state.projectDetailData = null;
    }

    async startProjectFromWizard(projectId) {
        if (!projectId) return;
        const numericId = parseInt(projectId, 10);
        if (isNaN(numericId) || numericId <= 0) return;

        this.state.startingProject = true;
        try {
            const res = await this.orm.call("project.manage", "action_dashboard_start_project", [numericId]);
            if (res && res.success) {
                if (this.notification) {
                    this.notification.add(res.message || "Project started successfully!", { type: "success" });
                }
                const updated = await this.orm.call("project.manage", "get_project_detail_dashboard", [numericId]);
                if (updated && !updated.error) {
                    this.state.projectDetailData = updated;
                }
                await this.loadData();
                if (this.state.selectedProjectId === numericId) {
                    await this.loadProjectScopes(numericId);
                }
            } else {
                if (this.notification) {
                    this.notification.add((res && res.error) || "Could not start project.", { type: "danger" });
                }
            }
        } catch (err) {
            console.error("Failed to start project:", err);
            if (this.notification) {
                this.notification.add("Failed to start project: " + (err.message || err), { type: "danger" });
            }
        } finally {
            this.state.startingProject = false;
        }
    }

    openProjectFromWizard(projectId) {
        this.closeProjectDetailWizard();
        this.openProject(projectId);
    }

    openProjectScopesFromWizard(projectId) {
        this.closeProjectDetailWizard();
        this.openProjectScopesTab(projectId);
    }
}

registry.category("actions").add("project_manage_dashboard", ProjectManageDashboard);
