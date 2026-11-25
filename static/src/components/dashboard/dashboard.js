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
                } else if (nextView === 'reviews') {
                    this.loadCustomerReviews();
                }
            }
        });

        onMounted(() => {
            if (this.state.activeMainView === 'projects') {
                this.scrollToProjectsTable();
            } else if (this.state.activeMainView === 'reviews') {
                this.loadCustomerReviews();
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
            mobileSelectedProjectId: null,
            mobileProjectDetailData: null,
            mobileProjectDetailLoading: false,
            projectCardsWizardOpen: false,
            projectCardsWizardTitle: "Projects",
            projectCardsWizardSubtitle: "",
            projectCardsWizardFilterType: "all",
            projectCardsWizardFilterValue: "",
            projectCardsWizardSearch: "",
            teamPerformanceWizardOpen: false,
            teamPerformanceLoading: false,
            teamPerformanceData: null,
            selectedPerformanceTeamId: 'all',
            teamPerformanceSearch: "",
            calendarTimeFilter: 'all',    // 'all', 'today', 'tomorrow', 'week', 'month'
            calendarViewMode: 'week',     // 'week' (7-col grid), 'month', 'agenda'
            calendarCategoryFilter: 'all', // 'all', 'documentation', 'implementation'
            calendarTypeFilter: 'task',  // strictly tasks only
            calendarStatusFilter: 'all', // 'all', 'overdue', 'in_progress', 'done'
            calendarYear: new Date().getFullYear(),
            calendarMonth: new Date().getMonth(), // 0-11
            calendarDate: new Date().getDate(),
            calendarTaskFilterScope: 'day', // 'day' (selected date), 'week', 'month', 'overdue'
            calendarSearchQuery: "",
            mobileCalendarViewMode: 'month', // 'month' (Month Grid) or 'week' (Timeline Week)
            mobileCalendarStatusFilter: 'all', // 'all', 'completed', 'due', 'not_started', 'in_progress'
            selectedTeamId: null,
            activeRoleView: null,
            selectedProjectId: null,
            projectScopesLoading: false,
            projectScopesData: null,
            activeCategoryFilter: 'all',  // 'all', 'documentation', 'implementation'
            activeStatusFilter: 'all',    // 'all', 'completed', 'in_progress', 'pending', 'overdue'
            selectedScopeName: null,      // specific scope filter if clicked
            searchQuery: "",
            scopePage: 1,
            scopePageSize: 10,
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
                selected_scopes: Array.from({length: 30}, (_, i) => i),
                scope_search_query: "",
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
            scopeDetailNotes: "",
            scopeDetailNotesSaving: false,
            scopeDetailEditingNotes: false,
            scopeDetailSubmitting: false,
            scopeDetailUploadOpen: false,
            scopeDetailUploadFile: null,
            scopeDetailUploadFilename: "",
            scopeDetailUploadFileSize: "",
            scopeDetailUploadNotes: "",
            scopeDetailUploadType: "deliverable",
            scopeDetailUploading: false,
            projectDetailWizardOpen: false,
            projectDetailLoading: false,
            projectDetailData: null,
            startingProject: false,
                        // Customer Reviews Hub State
            reviewsData: null,
            reviewsLoading: false,
            reviewFilterRating: 'all',  // 'all', '5', '4', '3', 'low'
            reviewFilterStatus: 'all',  // 'all', 'draft', 'submitted', 'under_review', 'approved'
            reviewFilterType: 'all',    // 'all', 'milestone', 'monthly', 'completion', 'ad_hoc'
            reviewProjectFilter: 'all', // 'all' or projectId
            reviewSearchQuery: "",
            reviewWizardOpen: false,
            reviewWizardSaving: false,
            reviewWizardShowMore: false,
            reviewWizardData: {},
            reviewDetailOpen: false,
            reviewDetailData: null,
            reviewDetailAckSaving: false,
            reviewDetailAckResponse: "",
            reviewDetailSendEmail: false,
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
            taskPage: 1,
            taskPageSize: 20,
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
        this.state.scopePage = 1;
        this.state.scopePageSize = 10;
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
        this.state.scopePage = 1;
        this.state.scopePageSize = 10;
        await this.loadData();
    }

    async onSelectProject(projectId, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        if (this.state.selectedProjectId === projectId) {
            this.state.selectedProjectId = null;
            this.state.projectScopesData = null;
            this.state.scopePage = 1;
            this.state.scopePageSize = 10;
            await this.loadData();
            return;
        }
        this.state.selectedProjectId = projectId;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        this.state.scopePage = 1;
        this.state.scopePageSize = 10;
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
            if (this.state.scopePage > 1 && res && res.scopes) {
                const maxPage = Math.max(1, Math.ceil(res.scopes.length / (this.state.scopePageSize || 10)));
                if (this.state.scopePage > maxPage) {
                    this.state.scopePage = maxPage;
                }
            }
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
        this.state.scopePage = 1;
    }

    setStatusFilter(status) {
        this.state.activeStatusFilter = status;
        this.state.scopePage = 1;
    }

    setScopeNameFilter(scopeName) {
        if (this.state.selectedScopeName === scopeName) {
            this.state.selectedScopeName = null;
        } else {
            this.state.selectedScopeName = scopeName;
        }
        this.state.scopePage = 1;
    }

    onScopeSelectChange(ev) {
        const val = ev.target.value;
        this.state.selectedScopeName = val ? val : null;
        this.state.scopePage = 1;
    }

    onScopeDropdownChange(ev) {
        this.onScopeSelectChange(ev);
    }

    onSearchChange(ev) {
        this.state.searchQuery = ev.target.value.toLowerCase().trim();
        this.state.scopePage = 1;
    }

    clearFilters() {
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        this.state.scopePage = 1;
        this.state.scopePageSize = 10;
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

    get paginatedScopes() {
        const list = this.filteredScopes;
        const page = this.state.scopePage || 1;
        const size = this.state.scopePageSize || 10;
        const start = (page - 1) * size;
        return list.slice(start, start + size);
    }

    get totalScopePages() {
        const total = this.filteredScopes.length;
        const size = this.state.scopePageSize || 10;
        return Math.max(1, Math.ceil(total / size));
    }

    get scopePaginationInfo() {
        const total = this.filteredScopes.length;
        if (!total) {
            return { start: 0, end: 0, total: 0 };
        }
        const page = this.state.scopePage || 1;
        const size = this.state.scopePageSize || 10;
        const start = (page - 1) * size + 1;
        const end = Math.min(page * size, total);
        return { start, end, total };
    }

    get hasMoreScopes() {
        const total = this.filteredScopes.length;
        const page = this.state.scopePage || 1;
        const size = this.state.scopePageSize || 10;
        return (page * size) < total;
    }

    nextScopePage() {
        if (this.state.scopePage < this.totalScopePages) {
            this.state.scopePage++;
            this.scrollToScopesTable();
        }
    }

    prevScopePage() {
        if (this.state.scopePage > 1) {
            this.state.scopePage--;
            this.scrollToScopesTable();
        }
    }

    loadMoreScopes() {
        const total = this.filteredScopes.length;
        const currentEnd = (this.state.scopePage || 1) * (this.state.scopePageSize || 10);
        if (currentEnd < total) {
            if (this.state.scopePage > 1) {
                this.state.scopePageSize = currentEnd + 10;
                this.state.scopePage = 1;
            } else {
                this.state.scopePageSize = (this.state.scopePageSize || 10) + 10;
            }
        }
    }

    setScopePageSize(size) {
        this.state.scopePageSize = parseInt(size) || 10;
        this.state.scopePage = 1;
    }

    scrollToScopesTable() {
        if (typeof document !== 'undefined') {
            const el = document.querySelector(".pm-scope-table-wrap");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        }
    }

    // ==================== ROLE PERMISSIONS & GETTERS ====================
    get canSeeTeamsRow() {
        const u = this.state.data?.user_info;
        if (!u) return false;
        return Boolean(u.is_ceo || u.is_vp || u.is_manager || u.is_admin || u.is_executive || u.can_see_all_teams);
    }

    // ==================== MOBILE ASSIGNED SCOPES & TASKS GETTERS ====================
    get isConsultantUser() {
        const u = this.state.data?.user_info;
        return Boolean(u?.is_consultant || u?.role_code === 'consultant');
    }

    get mobileAssignedScopes() {
        if (!this.state.projectScopesData || !this.state.projectScopesData.scopes) {
            return [];
        }
        let list = this.state.projectScopesData.scopes;
        const isConsultant = this.isConsultantUser;

        if (isConsultant) {
            const uid = this.state.data?.user_info?.id;
            const uname = (this.state.data?.user_info?.name || '').trim().toLowerCase();
            list = list.filter(s => {
                if (s.is_assigned_to_me !== undefined) {
                    return s.is_assigned_to_me;
                }
                if (!s.is_assigned && (!s.responsible_name || s.responsible_name === 'Unassigned' || !s.responsible_name.trim())) {
                    return false;
                }
                if (uid && s.responsible_user_ids && s.responsible_user_ids.includes(uid)) {
                    return true;
                }
                if (uname && s.responsible_name && s.responsible_name !== 'Unassigned') {
                    return s.responsible_name.toLowerCase().includes(uname);
                }
                return false;
            });
        } else {
            // For mobile view, filter out unassigned tasks
            list = list.filter(s => s.is_assigned !== false && s.responsible_name && s.responsible_name !== 'Unassigned' && s.responsible_name.trim() !== '');
        }

        return list;
    }

    get mobileUniqueScopes() {
        const assignedScopes = this.mobileAssignedScopes;
        const scopeMap = {};
        const unique = [];
        for (const s of assignedScopes) {
            const scName = s.scope_name || s.scope || 'Scope';
            if (!scopeMap[scName]) {
                scopeMap[scName] = {
                    name: scName,
                    scope_no: s.scope_no !== undefined ? s.scope_no : 0,
                    total: 0,
                    done: 0,
                };
                unique.push(scopeMap[scName]);
            }
            scopeMap[scName].total += 1;
            if (s.state === 'done') {
                scopeMap[scName].done += 1;
            }
        }
        return unique;
    }

    get mobileScopesStats() {
        const assignedScopes = this.mobileAssignedScopes;
        return {
            total_items: assignedScopes.length,
            done_items: assignedScopes.filter(s => s.state === 'done').length,
        };
    }

    get mobileFilteredScopes() {
        let list = this.mobileAssignedScopes;

        // Filter by category
        if (this.state.activeCategoryFilter === 'documentation') {
            list = list.filter(s => s.category && s.category.toLowerCase().includes('doc'));
        } else if (this.state.activeCategoryFilter === 'implementation') {
            list = list.filter(s => s.category && s.category.toLowerCase().includes('imp'));
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
            const q = this.state.searchQuery.toLowerCase();
            list = list.filter(s => 
                (s.item_id && s.item_id.toLowerCase().includes(q)) ||
                (s.name && s.name.toLowerCase().includes(q)) ||
                (s.scope_name && s.scope_name.toLowerCase().includes(q)) ||
                (s.responsible_name && s.responsible_name.toLowerCase().includes(q))
            );
        }

        return list;
    }

    get paginatedMobileScopes() {
        const list = this.mobileFilteredScopes;
        const page = this.state.scopePage || 1;
        const size = this.state.scopePageSize || 10;
        const start = (page - 1) * size;
        return list.slice(start, start + size);
    }

    get totalMobileScopePages() {
        const total = this.mobileFilteredScopes.length;
        const size = this.state.scopePageSize || 10;
        return Math.max(1, Math.ceil(total / size));
    }

    get hasMoreMobileScopes() {
        const total = this.mobileFilteredScopes.length;
        const page = this.state.scopePage || 1;
        const size = this.state.scopePageSize || 10;
        return (page * size) < total;
    }

    // ==================== UNIVERSAL TASKS HUB METHODS & GETTER ====================
    setTaskTab(tab) {
        this.state.taskTab = tab;
        this.state.taskPage = 1;
    }

    setTaskCategoryFilter(cat) {
        this.state.taskCategoryFilter = cat;
        this.state.taskPage = 1;
    }

    setTaskPriorityFilter(ev) {
        this.state.taskPriorityFilter = ev.target.value;
        this.state.taskPage = 1;
    }

    setTaskConsultantFilter(ev) {
        this.state.taskConsultantFilter = ev.target.value;
        this.state.taskPage = 1;
    }

    setTaskProjectFilter(ev) {
        this.state.taskProjectFilter = ev.target.value;
        this.state.taskPage = 1;
    }

    onTaskSearchChange(ev) {
        this.state.taskSearchQuery = ev.target.value.toLowerCase().trim();
        this.state.taskPage = 1;
    }

    clearTaskFilters() {
        this.state.taskTab = 'pending';
        this.state.taskCategoryFilter = 'all';
        this.state.taskPriorityFilter = 'all';
        this.state.taskConsultantFilter = 'all';
        this.state.taskProjectFilter = 'all';
        this.state.taskSearchQuery = '';
        this.state.taskPage = 1;
        this.state.taskPageSize = 20;
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

    get paginatedTasks() {
        const tasks = this.filteredTasks;
        const page = this.state.taskPage || 1;
        const size = this.state.taskPageSize || 20;
        const start = (page - 1) * size;
        return tasks.slice(start, start + size);
    }

    get totalTaskPages() {
        const total = this.filteredTasks.length;
        const size = this.state.taskPageSize || 20;
        return Math.max(1, Math.ceil(total / size));
    }

    get taskPaginationInfo() {
        const total = this.filteredTasks.length;
        if (!total) {
            return { start: 0, end: 0, total: 0 };
        }
        const page = this.state.taskPage || 1;
        const size = this.state.taskPageSize || 20;
        const start = (page - 1) * size + 1;
        const end = Math.min(page * size, total);
        return { start, end, total };
    }

    get hasMoreTasks() {
        const total = this.filteredTasks.length;
        const page = this.state.taskPage || 1;
        const size = this.state.taskPageSize || 20;
        return (page * size) < total;
    }

    nextTaskPage() {
        if (this.state.taskPage < this.totalTaskPages) {
            this.state.taskPage++;
            this.scrollToTasksTable();
        }
    }

    prevTaskPage() {
        if (this.state.taskPage > 1) {
            this.state.taskPage--;
            this.scrollToTasksTable();
        }
    }

    loadMoreTasks() {
        const total = this.filteredTasks.length;
        const currentLimit = (this.state.taskPage || 1) * (this.state.taskPageSize || 20);
        if (currentLimit < total) {
            this.state.taskPageSize = (this.state.taskPageSize || 20) + 20;
        }
    }

    scrollToTasksTable() {
        if (typeof document !== 'undefined') {
            const el = document.querySelector(".pm-mytasks-table-wrap");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }
    }

    // ==================== 5-VIEW TAB NAVIGATION METHODS ====================
    setActiveTab(tab) {
        if (tab !== 'projects') {
            this.state.mobileSelectedProjectId = null;
        }
        this.state.activeMainView = tab;
        if (tab === 'scopes' && !this.state.selectedProjectId) {
            const projs = (this.state.data && this.state.data.projects) || [];
            if (projs.length > 0) {
                this.selectProjectForScopes(projs[0].id);
            }
        } else if (tab === 'reviews' && !this.state.reviewsData) {
            this.loadCustomerReviews();
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
            if (this.state.activeMainView === 'reviews') {
                return section === 'reviews';
            }
            if (section === 'calendar' || section === 'reviews') {
                return false;
            }
            return true;
        }
        // Mobile view: strictly show only the active tab (home, projects, approvals, scopes, calendar, reviews)
        return this.isTabActive(section);
    }

    async selectProjectForScopes(projectId) {
        if (!projectId) return;
        this.state.selectedProjectId = projectId;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        this.state.scopePage = 1;
        this.state.scopePageSize = 10;
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

    setProjectRiskFilter(filter) {
        this.state.projectRiskFilter = filter;
    }

    setProjectConditionFilter(filter) {
        this.state.projectConditionFilter = filter;
    }

    setProjectHealthFilter(filter) {
        this.state.projectHealthFilter = filter;
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

    get topThreeTeams() {
        const backendTop3 = (this.state.data && this.state.data.top_3_teams) || [];
        const rawTeams = (backendTop3 && backendTop3.length >= 3) ? backendTop3 : ((this.state.data && this.state.data.teams) || []);
        if (!rawTeams.length) {
            return { p1: null, p2: null, p3: null, hasTeams: false, totalTeamsCount: 0 };
        }
        const teams = [...rawTeams];
        teams.sort((a, b) => {
            const bDone = b.completed_tasks_count || 0;
            const aDone = a.completed_tasks_count || 0;
            if (bDone !== aDone) return bDone - aDone;
            const bPct = b.completed_tasks_pct || 0;
            const aPct = a.completed_tasks_pct || 0;
            if (bPct !== aPct) return bPct - aPct;
            return (b.productivity || 0) - (a.productivity || 0);
        });

        const formatTeam = (tm, rank) => {
            if (!tm) return null;
            const done = tm.completed_tasks_count || 0;
            const pct = tm.completed_tasks_pct || 0;
            const score = (done * 10.0 + pct * 0.5).toFixed(1);
            return {
                ...tm,
                rank,
                score,
            };
        };

        const p1 = formatTeam(teams[0], 1);
        const p2 = formatTeam(teams[1], 2);
        const p3 = formatTeam(teams[2], 3);

        return {
            p1,
            p2,
            p3,
            hasTeams: true,
            totalTeamsCount: teams.length,
        };
    }

    get teamPodiumTop3() {
        const emps = (this.state.teamPerformanceData && this.state.teamPerformanceData.employees) || [];
        const p1 = emps.find(e => e.rank === 1) || emps[0] || null;
        const p2 = emps.find(e => e.rank === 2) || (emps.length > 1 ? emps[1] : null);
        const p3 = emps.find(e => e.rank === 3) || (emps.length > 2 ? emps[2] : null);
        return { p1, p2, p3 };
    }

    get filteredPerformanceEmployees() {
        const emps = (this.state.teamPerformanceData && this.state.teamPerformanceData.employees) || [];
        const query = (this.state.teamPerformanceSearch || "").trim().toLowerCase();
        if (!query) return emps;
        return emps.filter(e =>
            (e.name && e.name.toLowerCase().includes(query)) ||
            (e.job_title && e.job_title.toLowerCase().includes(query)) ||
            (e.team_str && e.team_str.toLowerCase().includes(query))
        );
    }

    async openTeamPerformanceWizard(teamId = 'all', ev = null) {
        if (ev) ev.stopPropagation();
        const targetTeamId = teamId || 'all';
        this.state.selectedPerformanceTeamId = targetTeamId;
        this.state.teamPerformanceWizardOpen = true;
        this.state.teamPerformanceLoading = true;
        try {
            const res = await this.orm.call("project.manage", "get_team_employee_performance", [targetTeamId]);
            if (res && !res.error) {
                this.state.teamPerformanceData = res;
            } else {
                if (this.notification) {
                    this.notification.add(res?.error || "Failed to load consultant performance.", { type: "danger" });
                }
            }
        } catch (err) {
            console.error("Failed to load consultant performance:", err);
            if (this.notification) {
                this.notification.add("Failed to load consultant performance.", { type: "danger" });
            }
        } finally {
            this.state.teamPerformanceLoading = false;
        }
    }

    filterPerformanceTeam(teamId) {
        this.openTeamPerformanceWizard(teamId);
    }

    closeTeamPerformanceWizard() {
        this.state.teamPerformanceWizardOpen = false;
        this.state.teamPerformanceData = null;
        this.state.teamPerformanceSearch = "";
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

    async selectMobileProject(projectId) {
        if (!projectId) return;
        this.state.mobileSelectedProjectId = projectId;
        this.state.mobileProjectDetailLoading = true;
        this.state.mobileProjectDetailData = null;
        try {
            const numericId = parseInt(projectId, 10);
            const data = await this.orm.call("project.manage", "get_project_detail_dashboard", [numericId]);
            if (data && !data.error) {
                this.state.mobileProjectDetailData = data;
            } else {
                this.state.mobileProjectDetailData = this.state.data?.projects?.find(p => p.id === projectId) || null;
            }
        } catch (err) {
            console.error("Failed to load project details on mobile:", err);
            this.state.mobileProjectDetailData = this.state.data?.projects?.find(p => p.id === projectId) || null;
        } finally {
            this.state.mobileProjectDetailLoading = false;
        }
    }

    backToMobileProjectsList() {
        this.state.mobileSelectedProjectId = null;
        this.state.mobileProjectDetailData = null;
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
        if (mode === 'today' || mode === 'today_tasks') {
            const now = new Date();
            this.state.calendarYear = now.getFullYear();
            this.state.calendarMonth = now.getMonth();
            this.state.calendarDate = now.getDate();
        }
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
        if (this.state.calendarViewMode === 'month') {
            if (this.state.calendarMonth === 0) {
                this.state.calendarMonth = 11;
                this.state.calendarYear -= 1;
            } else {
                this.state.calendarMonth -= 1;
            }
        } else if (this.state.calendarViewMode === 'today_tasks') {
            this.state.calendarViewMode = 'today';
            this.calendarPrevDay();
        } else if (this.state.calendarViewMode === 'today') {
            this.calendarPrevDay();
        } else {
            this.calendarPrevWeek();
        }
    }

    calendarNext() {
        if (this.state.calendarViewMode === 'month') {
            if (this.state.calendarMonth === 11) {
                this.state.calendarMonth = 0;
                this.state.calendarYear += 1;
            } else {
                this.state.calendarMonth += 1;
            }
        } else if (this.state.calendarViewMode === 'today_tasks') {
            this.state.calendarViewMode = 'today';
            this.calendarNextDay();
        } else if (this.state.calendarViewMode === 'today') {
            this.calendarNextDay();
        } else {
            this.calendarNextWeek();
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
        this.state.calendarTaskFilterScope = 'week';
        this.state.calendarTimeFilter = 'all';
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

    async createNewTaskForDate(dateIso) {
        if (!this.state.data?.user_info?.is_manager) {
            if (this.notification) {
                this.notification.add(_t("Only Project Managers can create new scopes or schedule tasks."), {
                    type: "warning",
                });
            }
            return;
        }
        const selIso = dateIso || this.calendarSelectedDateIso;
        const defaultCat = this.state.calendarCategoryFilter === 'implementation' ? 'Implementation' : 'Documentation';
        await this.openScopeWizard(null, null, {
            startDate: selIso,
            endDate: selIso,
            category: defaultCat,
            isCalendarSchedule: true,
            projectId: this.state.selectedProjectId || null,
        });
    }

    async createNewTaskForSelectedDate() {
        await this.createNewTaskForDate(this.calendarSelectedDateIso);
    }

    getEventPillClass(evt) {
        if (evt.status === 'done') {
            return 'pm-pill-green'; // Completed in green
        }
        if (evt.is_overdue || (evt.days_remaining !== undefined && evt.days_remaining <= 0)) {
            return 'pm-pill-red'; // Due in red
        }
        if (evt.status === 'todo' || !evt.status) {
            return 'pm-pill-yellow'; // Not started in yellow
        }
        if (evt.status === 'in_progress') {
            return 'pm-pill-blue'; // In progress in blue
        }
        if (evt.status === 'under_review') {
            return 'pm-pill-purple'; // Under review in purple
        }
        return 'pm-pill-blue';
    }

    getEventStatusPillLabel(evt) {
        if (evt.status === 'done') {
            return 'Completed';
        }
        if (evt.is_overdue) {
            return 'Overdue';
        }
        if (evt.days_remaining === 0) {
            return 'Due Today';
        }
        if (evt.status === 'todo') {
            return 'Not Started';
        }
        if (evt.status === 'in_progress') {
            return 'In Progress';
        }
        if (evt.status === 'under_review') {
            return 'Under Review';
        }
        return evt.status_label || 'Active';
    }

    get calendarWeekRangeTitle() {
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        if (this.state.calendarViewMode === 'today_tasks') {
            return `Showing all tasks scheduled or due for today`;
        }
        if (this.state.calendarViewMode === 'today') {
            return this.calendarIsSelectedDateToday ? "Today's Schedule & Deliverables" : `Schedule for ${this.calendarSelectedDateTitle}`;
        }
        if (this.state.calendarViewMode === 'month') {
            const year = this.state.calendarYear;
            const month = this.state.calendarMonth;
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            return `1 ${months[month]} – ${daysInMonth} ${months[month]} ${year}`;
        }
        if (this.state.calendarViewMode === 'agenda') {
            return `Timeline & Deadlines Agenda`;
        }
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayOfWeek = cur.getDay();
        const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
        const mon = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);
        const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);
        return `${mon.getDate()} ${months[mon.getMonth()]} – ${sun.getDate()} ${months[sun.getMonth()]} ${sun.getFullYear()}`;
    }

    openDateInWeekView(dateIso) {
        if (!dateIso) return;
        const parts = dateIso.split("-").map(Number);
        if (parts.length >= 3) {
            this.state.calendarYear = parts[0];
            this.state.calendarMonth = parts[1] - 1;
            this.state.calendarDate = parts[2];
        }
        this.state.calendarViewMode = 'week';
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
        const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);

        if (this.state.calendarViewMode === 'today_tasks') {
            const now = new Date();
            return `Today's Tasks – ${dayNames[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
        }
        if (this.state.calendarViewMode === 'today') {
            return `${dayNames[cur.getDay()]}, ${cur.getDate()} ${months[cur.getMonth()]} ${cur.getFullYear()}`;
        }
        if (this.state.calendarViewMode === 'month') {
            return `${months[this.state.calendarMonth]} ${this.state.calendarYear}`;
        }
        const dayOfWeek = cur.getDay();
        const diffToMon = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
        const mon = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + diffToMon);
        const sun = new Date(mon.getFullYear(), mon.getMonth(), mon.getDate() + 6);

        if (mon.getMonth() === sun.getMonth()) {
            return `${months[mon.getMonth()]} ${mon.getFullYear()}`;
        }
        if (mon.getFullYear() === sun.getFullYear()) {
            return `${months[mon.getMonth()].slice(0, 3)} – ${months[sun.getMonth()].slice(0, 3)} ${mon.getFullYear()}`;
        }
        return `${months[mon.getMonth()].slice(0, 3)} ${mon.getFullYear()} – ${months[sun.getMonth()].slice(0, 3)} ${sun.getFullYear()}`;
    }

    get filteredCalendarEvents() {
        let events = this.state.data.calendar_events || [];

        // Strictly show tasks only
        events = events.filter(e => e.type === 'task');

        // 1. Project filter
        if (this.state.selectedProjectId) {
            events = events.filter(e => e.project_id === this.state.selectedProjectId);
        }

        // 2. Team filter
        if (this.state.selectedTeamId) {
            events = events.filter(e => e.team_id === this.state.selectedTeamId);
        }

        // 3. Category filter (All / Documentation / Implementation)
        if (this.state.calendarCategoryFilter && this.state.calendarCategoryFilter !== 'all') {
            const cat = this.state.calendarCategoryFilter.toLowerCase();
            events = events.filter(e => (e.category || '').toLowerCase().includes(cat));
        }

        // 4. Status filter
        if (this.state.calendarStatusFilter && this.state.calendarStatusFilter !== 'all') {
            if (this.state.calendarStatusFilter === 'overdue' || this.state.calendarStatusFilter === 'due') {
                events = events.filter(e => e.is_overdue || e.days_remaining <= 0);
            } else if (this.state.calendarStatusFilter === 'done' || this.state.calendarStatusFilter === 'completed') {
                events = events.filter(e => e.status === 'done');
            } else if (this.state.calendarStatusFilter === 'todo' || this.state.calendarStatusFilter === 'not_started') {
                events = events.filter(e => e.status === 'todo');
            } else if (this.state.calendarStatusFilter === 'in_progress') {
                events = events.filter(e => e.status === 'in_progress');
            } else if (this.state.calendarStatusFilter === 'under_review') {
                events = events.filter(e => e.status === 'under_review' || e.approval_state === 'submitted');
            }
        }

        // 5. Search query
        if (this.state.calendarSearchQuery && this.state.calendarSearchQuery.trim()) {
            const q = this.state.calendarSearchQuery.trim().toLowerCase();
            events = events.filter(e => 
                (e.title || '').toLowerCase().includes(q) ||
                (e.code || '').toLowerCase().includes(q) ||
                (e.project_name || '').toLowerCase().includes(q) ||
                (e.responsible_name || '').toLowerCase().includes(q)
            );
        }

        // 6. Time filter (Today, Tomorrow, Week, Month, All)
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

    get calendarTodayTasks() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

        let allEvents = (this.state.data && this.state.data.calendar_events) ? 
                        this.state.data.calendar_events.filter(e => e.type === 'task') : [];

        // Project filter
        if (this.state.selectedProjectId) {
            allEvents = allEvents.filter(e => e.project_id === this.state.selectedProjectId);
        }
        // Team filter
        if (this.state.selectedTeamId) {
            allEvents = allEvents.filter(e => e.team_id === this.state.selectedTeamId);
        }
        // Category filter
        if (this.state.calendarCategoryFilter && this.state.calendarCategoryFilter !== 'all') {
            const cat = this.state.calendarCategoryFilter.toLowerCase();
            allEvents = allEvents.filter(e => (e.category || '').toLowerCase().includes(cat));
        }
        // Status filter
        if (this.state.calendarStatusFilter && this.state.calendarStatusFilter !== 'all') {
            if (this.state.calendarStatusFilter === 'overdue' || this.state.calendarStatusFilter === 'due') {
                allEvents = allEvents.filter(e => e.is_overdue || e.days_remaining <= 0);
            } else if (this.state.calendarStatusFilter === 'done' || this.state.calendarStatusFilter === 'completed') {
                allEvents = allEvents.filter(e => e.status === 'done');
            } else if (this.state.calendarStatusFilter === 'todo' || this.state.calendarStatusFilter === 'not_started') {
                allEvents = allEvents.filter(e => e.status === 'todo');
            } else if (this.state.calendarStatusFilter === 'in_progress') {
                allEvents = allEvents.filter(e => e.status === 'in_progress');
            } else if (this.state.calendarStatusFilter === 'under_review') {
                allEvents = allEvents.filter(e => e.status === 'under_review' || e.approval_state === 'submitted');
            }
        }
        // Search query
        if (this.state.calendarSearchQuery && this.state.calendarSearchQuery.trim()) {
            const q = this.state.calendarSearchQuery.trim().toLowerCase();
            allEvents = allEvents.filter(e => 
                (e.title || '').toLowerCase().includes(q) ||
                (e.code || '').toLowerCase().includes(q) ||
                (e.project_name || '').toLowerCase().includes(q) ||
                (e.responsible_name || '').toLowerCase().includes(q)
            );
        }

        return allEvents.filter(e => e.date === todayIso || (e.is_overdue && e.status !== 'done'));
    }

    get calendarTodayTasksStats() {
        const events = this.calendarTodayTasks;
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

        return {
            total: events.length,
            dueToday: events.filter(e => e.date === todayIso && !e.is_overdue && e.status !== 'done').length,
            overdue: events.filter(e => e.is_overdue && e.status !== 'done').length,
            inProgress: events.filter(e => e.status === 'in_progress').length,
            todo: events.filter(e => e.status === 'todo').length,
            completed: events.filter(e => e.status === 'done').length,
        };
    }

    get calendarDayTasks() {
        const pad = (n) => String(n).padStart(2, "0");
        const selIso = `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}-${pad(this.state.calendarDate)}`;

        let allEvents = (this.state.data && this.state.data.calendar_events) ? 
                        this.state.data.calendar_events.filter(e => e.type === 'task') : [];

        // Project filter
        if (this.state.selectedProjectId) {
            allEvents = allEvents.filter(e => e.project_id === this.state.selectedProjectId);
        }
        // Team filter
        if (this.state.selectedTeamId) {
            allEvents = allEvents.filter(e => e.team_id === this.state.selectedTeamId);
        }
        // Category filter
        if (this.state.calendarCategoryFilter && this.state.calendarCategoryFilter !== 'all') {
            const cat = this.state.calendarCategoryFilter.toLowerCase();
            allEvents = allEvents.filter(e => (e.category || '').toLowerCase().includes(cat));
        }
        // Status filter
        if (this.state.calendarStatusFilter && this.state.calendarStatusFilter !== 'all') {
            if (this.state.calendarStatusFilter === 'overdue' || this.state.calendarStatusFilter === 'due') {
                allEvents = allEvents.filter(e => e.is_overdue || e.days_remaining <= 0);
            } else if (this.state.calendarStatusFilter === 'done' || this.state.calendarStatusFilter === 'completed') {
                allEvents = allEvents.filter(e => e.status === 'done');
            } else if (this.state.calendarStatusFilter === 'todo' || this.state.calendarStatusFilter === 'not_started') {
                allEvents = allEvents.filter(e => e.status === 'todo');
            } else if (this.state.calendarStatusFilter === 'in_progress') {
                allEvents = allEvents.filter(e => e.status === 'in_progress');
            } else if (this.state.calendarStatusFilter === 'under_review') {
                allEvents = allEvents.filter(e => e.status === 'under_review' || e.approval_state === 'submitted');
            }
        }
        // Search query
        if (this.state.calendarSearchQuery && this.state.calendarSearchQuery.trim()) {
            const q = this.state.calendarSearchQuery.trim().toLowerCase();
            allEvents = allEvents.filter(e => 
                (e.title || '').toLowerCase().includes(q) ||
                (e.code || '').toLowerCase().includes(q) ||
                (e.project_name || '').toLowerCase().includes(q) ||
                (e.responsible_name || '').toLowerCase().includes(q)
            );
        }

        return allEvents.filter(e => e.date === selIso);
    }

    get calendarDayViewInfo() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        const dayNamesShort = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        return {
            dayName: dayNamesShort[cur.getDay()],
            dayFullName: dayNames[cur.getDay()],
            dayNum: cur.getDate(),
            fullDate: `${dayNames[cur.getDay()]}, ${cur.getDate()} ${months[cur.getMonth()]} ${cur.getFullYear()}`,
        };
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

        let allEvents = (this.state.data && this.state.data.calendar_events) ? 
                        this.state.data.calendar_events.filter(e => e.type === 'task') : [];

        // Project filter
        if (this.state.selectedProjectId) {
            allEvents = allEvents.filter(e => e.project_id === this.state.selectedProjectId);
        }
        // Team filter
        if (this.state.selectedTeamId) {
            allEvents = allEvents.filter(e => e.team_id === this.state.selectedTeamId);
        }
        // Category filter
        if (this.state.calendarCategoryFilter && this.state.calendarCategoryFilter !== 'all') {
            const cat = this.state.calendarCategoryFilter.toLowerCase();
            allEvents = allEvents.filter(e => (e.category || '').toLowerCase().includes(cat));
        }
        // Status filter
        if (this.state.calendarStatusFilter && this.state.calendarStatusFilter !== 'all') {
            if (this.state.calendarStatusFilter === 'overdue' || this.state.calendarStatusFilter === 'due') {
                allEvents = allEvents.filter(e => e.is_overdue || e.days_remaining <= 0);
            } else if (this.state.calendarStatusFilter === 'done' || this.state.calendarStatusFilter === 'completed') {
                allEvents = allEvents.filter(e => e.status === 'done');
            } else if (this.state.calendarStatusFilter === 'todo' || this.state.calendarStatusFilter === 'not_started') {
                allEvents = allEvents.filter(e => e.status === 'todo');
            } else if (this.state.calendarStatusFilter === 'in_progress') {
                allEvents = allEvents.filter(e => e.status === 'in_progress');
            } else if (this.state.calendarStatusFilter === 'under_review') {
                allEvents = allEvents.filter(e => e.status === 'under_review' || e.approval_state === 'submitted');
            }
        }
        // Search query
        if (this.state.calendarSearchQuery && this.state.calendarSearchQuery.trim()) {
            const q = this.state.calendarSearchQuery.trim().toLowerCase();
            allEvents = allEvents.filter(e => 
                (e.title || '').toLowerCase().includes(q) ||
                (e.code || '').toLowerCase().includes(q) ||
                (e.project_name || '').toLowerCase().includes(q) ||
                (e.responsible_name || '').toLowerCase().includes(q)
            );
        }

        const days = [];
        const dayNames = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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
                const isPast = dStr < todayIso;
                let label = `${days[dObj.getDay()]}, ${dObj.getDate()} ${months[dObj.getMonth()]} ${dObj.getFullYear()}`;
                groups[dStr] = {
                    dateIso: dStr,
                    label,
                    dayName: days[dObj.getDay()],
                    formattedDate: `${dObj.getDate()} ${months[dObj.getMonth()]} ${dObj.getFullYear()}`,
                    isToday: dStr === todayIso,
                    isTomorrow: dStr === tomIso,
                    isPastDue: isPast,
                    events: [],
                };
            }
            groups[dStr].events.push(e);
        }

        return Object.values(groups).sort((a, b) => a.dateIso.localeCompare(b.dateIso));
    }

    // ==================== MOBILE CALENDAR SPECIFIC METHODS & GETTERS ====================
    setMobileCalendarViewMode(mode) {
        this.state.mobileCalendarViewMode = mode;
    }

    toggleMobileCalendarViewMode() {
        this.state.mobileCalendarViewMode = this.state.mobileCalendarViewMode === 'month' ? 'week' : 'month';
    }

    setMobileCalendarStatusFilter(filter) {
        this.state.mobileCalendarStatusFilter = filter;
    }

    calendarPrevMonth() {
        if (this.state.calendarMonth === 0) {
            this.state.calendarMonth = 11;
            this.state.calendarYear -= 1;
        } else {
            this.state.calendarMonth -= 1;
        }
    }

    calendarNextMonth() {
        if (this.state.calendarMonth === 11) {
            this.state.calendarMonth = 0;
            this.state.calendarYear += 1;
        } else {
            this.state.calendarMonth += 1;
        }
    }

    selectMobileCalendarDay(day) {
        if (!day) return;
        this.state.calendarYear = day.year;
        this.state.calendarMonth = day.month;
        this.state.calendarDate = day.dayNum;
    }

    getMobileTaskStatusInfo(evt) {
        // Requirements:
        // Completed tasks in GREEN
        // Due tasks in RED
        // Not started in YELLOW
        // In progress in BLUE
        if (evt.status === 'done' || evt.status === 'completed') {
            return {
                status: 'completed',
                color: 'green',
                label: 'Completed',
                cardClass: 'pm-mob-cal-card-green',
                dotClass: 'dot-green',
                icon: 'fa-check-circle',
                accentColor: '#16a34a',
                bg: '#ecfdf5',
                borderColor: '#86efac',
            };
        }
        if (evt.is_overdue || (evt.days_remaining !== undefined && evt.days_remaining <= 0)) {
            return {
                status: 'due',
                color: 'red',
                label: 'Due',
                cardClass: 'pm-mob-cal-card-red',
                dotClass: 'dot-red',
                icon: 'fa-bell',
                accentColor: '#dc2626',
                bg: '#fef2f2',
                borderColor: '#fca5a5',
            };
        }
        if (evt.status === 'in_progress') {
            return {
                status: 'in_progress',
                color: 'blue',
                label: 'In Progress',
                cardClass: 'pm-mob-cal-card-blue',
                dotClass: 'dot-blue',
                icon: 'fa-clock-o',
                accentColor: '#2563eb',
                bg: '#eff6ff',
                borderColor: '#93c5fd',
            };
        }
        return {
            status: 'not_started',
            color: 'yellow',
            label: 'Not Started',
            cardClass: 'pm-mob-cal-card-yellow',
            dotClass: 'dot-yellow',
            icon: 'fa-circle-o',
            accentColor: '#d97706',
            bg: '#fffbeb',
            borderColor: '#fde047',
        };
    }

    get mobileCalendarDateTitle() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        const yy = String(cur.getFullYear()).slice(-2);
        return `${cur.getDate()} ${monthNames[cur.getMonth()]}, ${yy} ${dayNames[cur.getDay()]}`;
    }

    get mobileCalendarMonthYearTitle() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, 1);
        const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        return `${monthNames[cur.getMonth()]} ${cur.getFullYear()}`;
    }

    get mobileCalendarIsSelectedDateToday() {
        const now = new Date();
        return this.state.calendarYear === now.getFullYear() &&
               this.state.calendarMonth === now.getMonth() &&
               this.state.calendarDate === now.getDate();
    }

    get mobileCalendarMonthGrid() {
        const year = this.state.calendarYear;
        const month = this.state.calendarMonth;
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const selectedIso = `${year}-${pad(month + 1)}-${pad(this.state.calendarDate)}`;

        const firstDay = new Date(year, month, 1);
        const dayOfWeek = firstDay.getDay(); // 0 is Sun, 1 is Mon... 6 is Sat
        const paddingDays = dayOfWeek; // Sun-first: 0 pad for Sun
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
            cells.push({
                key: `prev_${d}`,
                dayNum: d,
                month: prevM,
                year: prevY,
                dateIso,
                isCurrentMonth: false,
                isToday: dateIso === todayIso,
                isSelected: dateIso === selectedIso,
                dots: [],
            });
        }

        // Current month days
        for (let d = 1; d <= daysInMonth; d++) {
            const dateIso = `${year}-${pad(month + 1)}-${pad(d)}`;
            const cellEvents = allEvents.filter(e => e.date === dateIso);

            const hasCompleted = cellEvents.some(e => e.status === 'done' || e.status === 'completed');
            const hasDue = cellEvents.some(e => (e.status !== 'done' && e.status !== 'completed') && (e.is_overdue || (e.days_remaining !== undefined && e.days_remaining <= 0)));
            const hasInProgress = cellEvents.some(e => e.status === 'in_progress' && !e.is_overdue && !(e.days_remaining !== undefined && e.days_remaining <= 0));
            const hasNotStarted = cellEvents.some(e => (e.status === 'todo' || !e.status) && !e.is_overdue && !(e.days_remaining !== undefined && e.days_remaining <= 0));

            const dots = [];
            if (hasDue) dots.push('red');
            if (hasInProgress) dots.push('blue');
            if (hasNotStarted) dots.push('yellow');
            if (hasCompleted) dots.push('green');

            cells.push({
                key: `cur_${d}`,
                dayNum: d,
                month,
                year,
                dateIso,
                isCurrentMonth: true,
                isToday: dateIso === todayIso,
                isSelected: (d === this.state.calendarDate),
                dots,
                hasTasks: cellEvents.length > 0,
            });
        }

        // Next month trailing days to complete 35 or 42 cells
        const totalCells = cells.length <= 35 ? 35 : 42;
        const remaining = totalCells - cells.length;
        const nextM = month === 11 ? 0 : month + 1;
        const nextY = month === 11 ? year + 1 : year;

        for (let d = 1; d <= remaining; d++) {
            const dateIso = `${nextY}-${pad(nextM + 1)}-${pad(d)}`;
            cells.push({
                key: `next_${d}`,
                dayNum: d,
                month: nextM,
                year: nextY,
                dateIso,
                isCurrentMonth: false,
                isToday: dateIso === todayIso,
                isSelected: dateIso === selectedIso,
                dots: [],
            });
        }

        return cells;
    }

    get mobileCalendarWeekStripDays() {
        const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate);
        const dayOfWeek = cur.getDay(); // 0 is Sun
        const sunday = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() - dayOfWeek);

        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
        const selectedIso = `${cur.getFullYear()}-${pad(cur.getMonth() + 1)}-${pad(cur.getDate())}`;

        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const allEvents = this.filteredCalendarEvents;

        const days = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + i);
            const dateIso = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
            const dayEvents = allEvents.filter(e => e.date === dateIso);

            const hasCompleted = dayEvents.some(e => e.status === 'done' || e.status === 'completed');
            const hasDue = dayEvents.some(e => (e.status !== 'done' && e.status !== 'completed') && (e.is_overdue || (e.days_remaining !== undefined && e.days_remaining <= 0)));
            const hasInProgress = dayEvents.some(e => e.status === 'in_progress' && !e.is_overdue && !(e.days_remaining !== undefined && e.days_remaining <= 0));
            const hasNotStarted = dayEvents.some(e => (e.status === 'todo' || !e.status) && !e.is_overdue && !(e.days_remaining !== undefined && e.days_remaining <= 0));

            const dots = [];
            if (hasDue) dots.push('red');
            if (hasInProgress) dots.push('blue');
            if (hasNotStarted) dots.push('yellow');
            if (hasCompleted) dots.push('green');

            days.push({
                dayName: dayNames[i],
                dayNum: d.getDate(),
                year: d.getFullYear(),
                month: d.getMonth(),
                dateIso,
                isToday: dateIso === todayIso,
                isSelected: dateIso === selectedIso,
                taskCount: dayEvents.length,
                dots,
            });
        }
        return days;
    }

    get mobileCalendarSelectedDayTasks() {
        const pad = (n) => String(n).padStart(2, "0");
        const selectedIso = `${this.state.calendarYear}-${pad(this.state.calendarMonth + 1)}-${pad(this.state.calendarDate)}`;
        let events = this.filteredCalendarEvents.filter(e => e.date === selectedIso);

        if (this.state.mobileCalendarStatusFilter && this.state.mobileCalendarStatusFilter !== 'all') {
            const f = this.state.mobileCalendarStatusFilter;
            events = events.filter(e => {
                const info = this.getMobileTaskStatusInfo(e);
                return info.status === f || info.color === f;
            });
        }

        const fallbackTimes = ["9:00 AM - 10:15 AM", "11:00 AM - 12:20 PM", "12:40 PM - 1:30 PM", "2:00 PM - 3:15 PM", "3:45 PM - 4:45 PM", "5:00 PM - 6:00 PM"];

        return events.map((e, idx) => {
            const info = this.getMobileTaskStatusInfo(e);
            const initials = e.responsible_name ? 
                e.responsible_name.split(' ').map(n => n[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() : 'PM';
            const displayTime = e.start_date && e.end_date && e.start_date !== e.end_date ?
                `${e.start_date} - ${e.end_date}` :
                (fallbackTimes[idx % fallbackTimes.length]);
            return {
                ...e,
                statusInfo: info,
                initials,
                displayTime,
            };
        });
    }

    get mobileCalendarTimelineSlots() {
        const slots = [
            { hour: '8 AM', timeLabel: '8:00 AM', events: [] },
            { hour: '9 AM', timeLabel: '9:00 AM', events: [] },
            { hour: '10 AM', timeLabel: '10:00 AM', events: [] },
            { hour: '11 AM', timeLabel: '11:00 AM', events: [] },
            { hour: '12 PM', timeLabel: '12:00 PM', events: [] },
            { hour: '1 PM', timeLabel: '1:00 PM', events: [] },
            { hour: '2 PM', timeLabel: '2:00 PM', events: [] },
            { hour: '3 PM', timeLabel: '3:00 PM', events: [] },
            { hour: '4 PM', timeLabel: '4:00 PM', events: [] },
            { hour: '5 PM', timeLabel: '5:00 PM', events: [] },
        ];

        const dayTasks = this.mobileCalendarSelectedDayTasks;
        dayTasks.forEach((t, idx) => {
            const slotIdx = (idx * 2 + 1) % slots.length;
            slots[slotIdx].events.push(t);
        });

        return slots;
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

    get wizardProjectName() {
        const curProjId = this.state.wizardData?.project_id;
        if (curProjId && this.state.data?.all_projects_filter) {
            const found = this.state.data.all_projects_filter.find(p => p.id === parseInt(curProjId));
            if (found) return found.name;
        }
        return this.state.projectScopesData?.project?.name || (this.state.data?.all_projects_filter?.[0]?.name) || '';
    }

    async onWizardProjectChange(ev) {
        const val = ev.target.value;
        const projId = val ? parseInt(val) : null;
        if (!projId) return;
        this.state.wizardData.project_id = projId;
        try {
            const scopesRes = await this.orm.call("project.manage", "get_project_scopes_dashboard", [projId]);
            this.state.projectScopesData = scopesRes;
            if (scopesRes && scopesRes.available_scopes && scopesRes.available_scopes.length > 0) {
                if (!scopesRes.available_scopes.includes(this.state.wizardData.scope)) {
                    this.state.wizardData.scope = scopesRes.available_scopes[0];
                }
            }
        } catch (err) {
            console.error("Failed to load project scopes on project change:", err);
        }
    }

    async openScopeWizard(item = null, ev = null, options = {}) {
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
                project_id: item.project_id || this.state.selectedProjectId || (this.state.projectScopesData && this.state.projectScopesData.project && this.state.projectScopesData.project.id) || null,
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
                isCalendarSchedule: false,
            };
        } else {
            let targetProjId = options.projectId || this.state.selectedProjectId;
            if (!targetProjId && this.state.projectScopesData?.project?.id) {
                targetProjId = this.state.projectScopesData.project.id;
            }
            if (!targetProjId && this.state.data?.all_projects_filter && this.state.data.all_projects_filter.length > 0) {
                targetProjId = this.state.data.all_projects_filter[0].id;
            }

            if (targetProjId && (!this.state.projectScopesData || this.state.projectScopesData.project?.id !== targetProjId)) {
                try {
                    const scopesRes = await this.orm.call("project.manage", "get_project_scopes_dashboard", [targetProjId]);
                    this.state.projectScopesData = scopesRes;
                } catch (err) {
                    console.error("Failed to load project scopes for wizard:", err);
                }
            }

            const defaultScope = this.state.selectedScopeName || (this.state.projectScopesData && this.state.projectScopesData.available_scopes && this.state.projectScopesData.available_scopes[0]) || 'Project Initiation & Governance';
            const cat = options.category || (this.state.activeCategoryFilter === 'implementation' ? 'Implementation' : 'Documentation');

            this.state.wizardData = {
                id: null,
                project_id: targetProjId || null,
                scope: defaultScope,
                category: cat,
                name: '',
                item_type: '',
                priority: '0',
                responsible_ids: [],
                responsible_id: '',
                start_date: options.startDate || '',
                end_date: options.endDate || options.startDate || '',
                state: 'todo',
                isCalendarSchedule: Boolean(options.isCalendarSchedule),
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

    parseInt(val, radix = 10) {
        return parseInt(val, radix);
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
        if (!this.state.wizardData.scope || !this.state.wizardData.scope.trim()) {
            if (this.notification) {
                this.notification.add("Scope (Functional Area) is required.", { type: "warning" });
            }
            return;
        }
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
                is_calendar_schedule: Boolean(this.state.wizardData.isCalendarSchedule),
            };

            let updated = null;
            if (this.state.wizardData.id) {
                updated = await this.orm.call("project.manage", "save_scope_inline", [this.state.wizardData.id, vals]);
            } else {
                const projectId = this.state.wizardData.project_id || (this.state.projectScopesData && this.state.projectScopesData.project && this.state.projectScopesData.project.id);
                if (!projectId) {
                    if (this.notification) {
                        this.notification.add("Please select a project.", { type: "warning" });
                    }
                    this.state.savingScope = false;
                    return;
                }
                updated = await this.orm.call("project.manage", "create_scope_from_dashboard", [projectId, vals]);
            }

            if (updated && !updated.error) {
                this.state.projectScopesData = updated;
                if (this.notification) {
                    const msg = updated.message || (this.state.wizardData.id ? "Scope task saved!" : (this.state.wizardData.isCalendarSchedule ? "Task scheduled successfully!" : "New scope task created!"));
                    this.notification.add(msg, { type: "success" });
                }

                if (andNext && this.state.wizardData.id) {
                    const curId = this.state.wizardData.id;
                    const scopes = this.filteredScopes;
                    const idx = scopes.findIndex(s => s.id === curId);
                    if (idx !== -1 && idx < scopes.length - 1) {
                        const nextItem = scopes[idx + 1];
                        const nextPage = Math.floor((idx + 1) / (this.state.scopePageSize || 10)) + 1;
                        this.state.scopePage = nextPage;
                        this.openScopeWizard(nextItem);
                        return;
                    }
                }
                this.closeScopeWizard();
                await this.loadData();
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
        this.state.reviewProjectFilter = projectId ? String(projectId) : "all";
        this.setActiveTab('reviews');
        this.loadCustomerReviews(projectId);
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
            const res = await this.orm.call("project.manage", "action_dashboard_submit_scope", [], { scope_id: scopeId });
            if (res && res.error) {
                if (this.notification) {
                    this.notification.add(res.error, { type: "danger" });
                }
                return;
            }
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
                this.notification.add(err.message || "Could not submit task.", { type: "danger" });
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
                selected_scopes: (meta.standard_scopes && meta.standard_scopes.length > 0) ? meta.standard_scopes.map(s => s.scope_no) : Array.from({length: 30}, (_, i) => i),
                scope_search_query: "",
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

    get filteredStandardScopes() {
        const scopes = (this.state.projectFormData && this.state.projectFormData.standard_scopes) || [];
        const q = (this.state.newProjectData && this.state.newProjectData.scope_search_query || "").toLowerCase().trim();
        if (!q) return scopes;
        return scopes.filter(s =>
            (s.name && s.name.toLowerCase().includes(q)) ||
            String(s.scope_no).includes(q)
        );
    }

    isStandardScopeSelected(scopeNo) {
        const selected = (this.state.newProjectData && this.state.newProjectData.selected_scopes) || [];
        return selected.includes(scopeNo);
    }

    toggleStandardScope(scopeNo) {
        if (!this.state.newProjectData.selected_scopes) {
            this.state.newProjectData.selected_scopes = [];
        }
        const idx = this.state.newProjectData.selected_scopes.indexOf(scopeNo);
        if (idx === -1) {
            this.state.newProjectData.selected_scopes.push(scopeNo);
        } else {
            this.state.newProjectData.selected_scopes.splice(idx, 1);
        }
    }

    selectAllStandardScopes() {
        const scopes = (this.state.projectFormData && this.state.projectFormData.standard_scopes) || [];
        this.state.newProjectData.selected_scopes = scopes.map(s => s.scope_no);
    }

    deselectAllStandardScopes() {
        this.state.newProjectData.selected_scopes = [];
    }

    get selectedStandardScopesTasksCount() {
        const scopes = (this.state.projectFormData && this.state.projectFormData.standard_scopes) || [];
        const selected = (this.state.newProjectData && this.state.newProjectData.selected_scopes) || [];
        const selSet = new Set(selected);
        return scopes.filter(s => selSet.has(s.scope_no)).reduce((acc, s) => acc + (s.tasks_count || 0), 0);
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
        if (data.load_standard_scopes && (!data.selected_scopes || data.selected_scopes.length === 0)) {
            if (this.notification) this.notification.add("Please select at least one standard scope or turn off the pre-populate toggle.", { type: "warning" });
            return;
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
                if (this.state.mobileSelectedProjectId === updatedId) {
                    await this.selectMobileProject(updatedId);
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
        if (!this.state.data.user_info.is_manager && !this.state.data.user_info.is_admin && !this.state.data.user_info.is_executive) {
            if (this.notification) {
                this.notification.add("Team Leads and Consultants cannot create new teams.", { type: "warning" });
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
            const res = await this.orm.call("project.manage", "action_dashboard_submit_scope", [], { scope_id: taskId });
            if (res && res.error) {
                if (this.notification) {
                    this.notification.add(res.error, { type: "danger" });
                }
                return;
            }
            if (this.notification) {
                this.notification.add("Task marked complete and submitted for review", { type: "success" });
            }
            await this.loadData();
        } catch (err) {
            console.error("Failed to submit task:", err);
            if (this.notification) {
                this.notification.add(err.message || "Could not submit task.", { type: "danger" });
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
                this.state.scopeDetailNotes = data.notes || data.submission_notes || "";
                this.state.scopeDetailEditingNotes = false;
                this.state.scopeDetailUploadOpen = false;
                this.state.scopeDetailUploadFile = null;
                this.state.scopeDetailUploadFilename = "";
                this.state.scopeDetailUploadFileSize = "";
                this.state.scopeDetailUploadNotes = "";
                this.state.scopeDetailUploadType = "deliverable";
                this.state.scopeDetailUploading = false;
                this.state.scopeDetailNotesSaving = false;
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
        this.state.scopeDetailNotes = "";
        this.state.scopeDetailEditingNotes = false;
        this.state.scopeDetailUploadOpen = false;
        this.state.scopeDetailUploadFile = null;
        this.state.scopeDetailUploadFilename = "";
        this.state.scopeDetailUploadFileSize = "";
        this.state.scopeDetailUploadNotes = "";
        this.state.scopeDetailUploadType = "deliverable";
        this.state.scopeDetailUploading = false;
        this.state.scopeDetailNotesSaving = false;
        this.state.scopeDetailSubmitting = false;
    }

    async submitTaskFromModal(scopeId) {
        if (!scopeId) return;
        this.state.scopeDetailSubmitting = true;
        try {
            const res = await this.orm.call("project.manage", "action_dashboard_submit_scope", [scopeId]);
            if (res && res.error) {
                if (this.notification) this.notification.add(res.error, { type: "danger" });
                return;
            }
            if (this.notification) {
                this.notification.add("Task marked complete and submitted for review.", { type: "success" });
            }
            const updated = await this.orm.call("project.manage.scope", "get_scope_details_dashboard", [scopeId]);
            if (updated && !updated.error) {
                this.state.scopeDetailData = updated;
            }
            await this.loadData();
            if (this.state.selectedProjectId) {
                await this.loadProjectScopes(this.state.selectedProjectId);
            }
        } catch (err) {
            console.error("Failed to submit task from modal:", err);
            const msg = (err && err.data && err.data.message) || (err && err.message) || "Could not submit task.";
            if (this.notification) this.notification.add(msg, { type: "danger" });
        } finally {
            this.state.scopeDetailSubmitting = false;
        }
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

    async saveScopeDetailNotes() {
        if (!this.state.scopeDetailData || !this.state.scopeDetailData.id) return;
        if (this.state.scopeDetailData.can_modify_documents === false) {
            if (this.notification) this.notification.add("You are not authorized to edit this task at the current approval stage.", { type: "danger" });
            return;
        }
        this.state.scopeDetailNotesSaving = true;
        try {
            const res = await this.orm.call("project.manage.scope", "update_scope_notes_dashboard", [
                this.state.scopeDetailData.id,
                this.state.scopeDetailNotes || ""
            ]);
            if (res && !res.error) {
                this.state.scopeDetailData = res;
                if (res.notes !== undefined) {
                    this.state.scopeDetailNotes = res.notes;
                }
                this.state.scopeDetailEditingNotes = false;
                if (this.notification) {
                    this.notification.add("Notes & description saved successfully.", { type: "success" });
                }
                await this.loadData();
            } else {
                if (this.notification) this.notification.add((res && res.error) || "Could not save notes.", { type: "danger" });
            }
        } catch (err) {
            console.error("Failed to save notes:", err);
            if (this.notification) this.notification.add("Failed to save notes.", { type: "danger" });
        } finally {
            this.state.scopeDetailNotesSaving = false;
        }
    }

    toggleModalUploadSection() {
        this.state.scopeDetailUploadOpen = !this.state.scopeDetailUploadOpen;
        if (!this.state.scopeDetailUploadOpen) {
            this.cancelModalDocumentUpload();
        }
    }

    onModalFileSelected(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        this.state.scopeDetailUploadFile = file;
        this.state.scopeDetailUploadFilename = file.name;
        const sizeKb = file.size / 1024.0;
        this.state.scopeDetailUploadFileSize = sizeKb < 1024 ? `${sizeKb.toFixed(1)} KB` : `${(sizeKb / 1024.0).toFixed(1)} MB`;
        this.state.scopeDetailUploadOpen = true;
    }

    cancelModalDocumentUpload() {
        this.state.scopeDetailUploadFile = null;
        this.state.scopeDetailUploadFilename = "";
        this.state.scopeDetailUploadFileSize = "";
        this.state.scopeDetailUploadNotes = "";
        this.state.scopeDetailUploadOpen = false;
        const fileInput = document.getElementById("pmModalDocFileInput");
        if (fileInput) fileInput.value = "";
    }

    async confirmModalDocumentUpload(scopeId) {
        if (!this.state.scopeDetailUploadFile || !scopeId) {
            if (this.notification) this.notification.add("Please select a file to upload.", { type: "warning" });
            return;
        }
        if (this.state.scopeDetailData && this.state.scopeDetailData.can_modify_documents === false) {
            if (this.notification) this.notification.add("You are not authorized to upload files for this task at the current approval stage.", { type: "danger" });
            return;
        }
        const file = this.state.scopeDetailUploadFile;
        const notes = this.state.scopeDetailUploadNotes || "";
        const docType = this.state.scopeDetailUploadType || "deliverable";
        this.state.scopeDetailUploading = true;

        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const res = await this.orm.call("project.manage.scope", "upload_document_to_scope_dashboard", [
                    scopeId,
                    e.target.result,
                    file.name,
                    docType,
                    notes
                ]);
                if (res && !res.error) {
                    this.state.scopeDetailData = res;
                    if (res.notes && !this.state.scopeDetailNotes) {
                        this.state.scopeDetailNotes = res.notes;
                    }
                    this.cancelModalDocumentUpload();
                    if (this.notification) {
                        this.notification.add(`Document "${file.name}" uploaded successfully with notes.`, { type: "success" });
                    }
                    await this.loadData();
                } else {
                    if (this.notification) this.notification.add((res && res.error) || "Failed to upload document.", { type: "danger" });
                }
            } catch (err) {
                console.error("Failed to upload document:", err);
                if (this.notification) this.notification.add("Failed to upload document.", { type: "danger" });
            } finally {
                this.state.scopeDetailUploading = false;
            }
        };
        reader.readAsDataURL(file);
    }

    async deleteModalDocument(scopeId, docId, isAttachment = false) {
        if (!scopeId || !docId) return;
        if (this.state.scopeDetailData && this.state.scopeDetailData.can_modify_documents === false) {
            if (this.notification) this.notification.add("You are not authorized to delete documents for this task at the current approval stage.", { type: "danger" });
            return;
        }
        if (!confirm("Are you sure you want to delete this document?")) return;
        try {
            const res = await this.orm.call("project.manage.scope", "delete_scope_document_dashboard", [
                scopeId,
                docId,
                Boolean(isAttachment)
            ]);
            if (res && !res.error) {
                this.state.scopeDetailData = res;
                if (this.notification) {
                    this.notification.add("Document removed successfully.", { type: "info" });
                }
                await this.loadData();
            } else {
                if (this.notification) this.notification.add((res && res.error) || "Failed to delete document.", { type: "danger" });
            }
        } catch (err) {
            console.error("Failed to delete document:", err);
            const msg = (err && err.data && err.data.message) || (err && err.message) || "Failed to delete document.";
            if (this.notification) this.notification.add(msg, { type: "danger" });
        }
    }

    async onModalDocumentUpload(ev, scopeId) {
        this.onModalFileSelected(ev);
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

    // =========================================================================
    // CUSTOMER REVIEWS HUB METHODS & GETTERS
    // =========================================================================
    async loadCustomerReviews(projectId = null) {
        this.state.reviewsLoading = true;
        try {
            const pId = projectId || (this.state.reviewProjectFilter !== 'all' ? this.state.reviewProjectFilter : null);
            const res = await this.orm.call("project.manage", "get_customer_reviews_dashboard", [pId]);
            if (res && !res.error) {
                this.state.reviewsData = res;
            }
        } catch (err) {
            console.error("Failed to load customer reviews:", err);
            if (this.notification) {
                this.notification.add("Could not load customer reviews.", { type: "danger" });
            }
        } finally {
            this.state.reviewsLoading = false;
        }
    }

    get filteredCustomerReviews() {
        if (!this.state.reviewsData || !this.state.reviewsData.reviews) return [];
        let list = this.state.reviewsData.reviews;

        // Project filter
        if (this.state.reviewProjectFilter && this.state.reviewProjectFilter !== 'all') {
            const pId = parseInt(this.state.reviewProjectFilter, 10);
            list = list.filter(r => r.project_id === pId);
        }

        // Rating filter
        if (this.state.reviewFilterRating && this.state.reviewFilterRating !== 'all') {
            if (this.state.reviewFilterRating === 'low') {
                list = list.filter(r => r.rating_value <= 2);
            } else {
                const rVal = parseInt(this.state.reviewFilterRating, 10);
                list = list.filter(r => r.rating_value === rVal);
            }
        }

        // Status filter
        if (this.state.reviewFilterStatus && this.state.reviewFilterStatus !== 'all') {
            list = list.filter(r => r.state === this.state.reviewFilterStatus);
        }

        // Type filter
        if (this.state.reviewFilterType && this.state.reviewFilterType !== 'all') {
            list = list.filter(r => r.review_type === this.state.reviewFilterType);
        }

        // Search Query
        if (this.state.reviewSearchQuery && this.state.reviewSearchQuery.trim()) {
            const q = this.state.reviewSearchQuery.trim().toLowerCase();
            list = list.filter(r =>
                (r.name && r.name.toLowerCase().includes(q)) ||
                (r.partner_name && r.partner_name.toLowerCase().includes(q)) ||
                (r.reviewer_name && r.reviewer_name.toLowerCase().includes(q)) ||
                (r.project_name && r.project_name.toLowerCase().includes(q)) ||
                (r.feedback && r.feedback.toLowerCase().includes(q)) ||
                (r.strengths && r.strengths.toLowerCase().includes(q)) ||
                (r.areas_for_improvement && r.areas_for_improvement.toLowerCase().includes(q))
            );
        }

        return list;
    }

    openRecordReviewWizard(review = null, preselectedProjectId = null) {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        const todayIso = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;

        const projects = this.state.reviewsData?.projects || [];
        let pId = review ? review.project_id : (preselectedProjectId || (projects.length > 0 ? projects[0].id : ""));
        let proj = projects.find(p => p.id === parseInt(pId, 10)) || projects[0] || null;

        this.state.reviewWizardShowMore = false;
        this.state.reviewWizardData = {
            id: review ? review.id : null,
            name: review ? review.name : "",
            project_id: pId || (proj ? proj.id : ""),
            partner_id: proj ? proj.partner_id : "",
            partner_name: review ? review.partner_name : (proj ? proj.partner_name : ""),
            reviewer_name: review ? review.reviewer_name : (proj ? (proj.coordinator_name || proj.partner_name) : ""),
            reviewer_email: review ? review.reviewer_email : (proj ? proj.coordinator_email : ""),
            reviewer_phone: review ? review.reviewer_phone : (proj ? proj.coordinator_phone : ""),
            review_date: review ? review.review_date_iso : todayIso,
            review_type: review ? review.review_type : "milestone",
            rating: review ? String(review.rating_value) : "5",
            nps_score: review ? (review.nps_score || "9") : "9",
            feedback: review ? review.feedback : "",
            strengths: review ? review.strengths : "",
            areas_for_improvement: review ? review.areas_for_improvement : "",
            state: review ? review.state : "draft",
        };
        this.state.reviewWizardOpen = true;
    }

    closeRecordReviewWizard() {
        this.state.reviewWizardOpen = false;
        this.state.reviewWizardShowMore = false;
        this.state.reviewWizardData = {};
    }

    onReviewWizardProjectChange(ev) {
        const pId = parseInt(ev.target.value, 10);
        this.state.reviewWizardData.project_id = pId;
        const projects = this.state.reviewsData?.projects || [];
        const proj = projects.find(p => p.id === pId);
        if (proj) {
            this.state.reviewWizardData.partner_id = proj.partner_id;
            this.state.reviewWizardData.partner_name = proj.partner_name;
            if (!this.state.reviewWizardData.reviewer_name || this.state.reviewWizardData.reviewer_name === 'Client') {
                this.state.reviewWizardData.reviewer_name = proj.coordinator_name || proj.partner_name;
            }
            if (!this.state.reviewWizardData.reviewer_email) {
                this.state.reviewWizardData.reviewer_email = proj.coordinator_email;
            }
            if (!this.state.reviewWizardData.reviewer_phone) {
                this.state.reviewWizardData.reviewer_phone = proj.coordinator_phone;
            }
        }
    }

    setReviewWizardRating(stars) {
        this.state.reviewWizardData.rating = String(stars);
    }

    async saveReviewWizard(doSubmit = true) {
        if (this.state.reviewWizardSaving) return;
        const d = this.state.reviewWizardData;
        const projects = this.state.reviewsData?.projects || [];
        if (!d.project_id && projects.length > 0) {
            d.project_id = projects[0].id;
            d.partner_id = projects[0].partner_id;
        }
        if (!d.project_id) {
            if (this.notification) this.notification.add("Please select a project.", { type: "warning" });
            return;
        }

        const title = (d.name && d.name.trim()) ? d.name.trim() : (d.reviewer_name ? `${d.reviewer_name.trim()} Feedback` : "Customer Review");

        this.state.reviewWizardSaving = true;
        try {
            const vals = {
                name: title,
                project_id: d.project_id,
                partner_id: d.partner_id || false,
                reviewer_name: d.reviewer_name || "",
                reviewer_email: d.reviewer_email || "",
                reviewer_phone: d.reviewer_phone || "",
                review_date: d.review_date || false,
                review_type: d.review_type || "milestone",
                rating: String(d.rating || "5"),
                nps_score: d.nps_score || false,
                feedback: d.feedback || "",
                strengths: d.strengths || "",
                areas_for_improvement: d.areas_for_improvement || "",
                do_submit: doSubmit,
            };
            const res = await this.orm.call("project.manage", "save_customer_review_dashboard", [vals, d.id || false]);
            if (res && res.success) {
                this.state.reviewsData = res.data;
                if (this.notification) {
                    this.notification.add(res.message || "Customer review saved successfully!", { type: "success" });
                }
                this.closeRecordReviewWizard();
            } else if (res && res.error) {
                if (this.notification) this.notification.add(res.error, { type: "danger" });
            }
        } catch (err) {
            console.error("Failed to save review:", err);
            if (this.notification) this.notification.add("Failed to save review.", { type: "danger" });
        } finally {
            this.state.reviewWizardSaving = false;
        }
    }

    openReviewDetail(review) {
        this.state.reviewDetailData = review;
        this.state.reviewDetailAckResponse = review.internal_response || "";
        this.state.reviewDetailSendEmail = !review.response_sent;
        this.state.reviewDetailOpen = true;
    }

    closeReviewDetail() {
        this.state.reviewDetailOpen = false;
        this.state.reviewDetailData = null;
    }

    async confirmReviewAcknowledge(sendEmail = false) {
        if (!this.state.reviewDetailData || this.state.reviewDetailAckSaving) return;
        this.state.reviewDetailAckSaving = true;
        try {
            const revId = this.state.reviewDetailData.id;
            const respText = this.state.reviewDetailAckResponse || "";
            const res = await this.orm.call("project.manage", "acknowledge_customer_review_dashboard", [
                revId,
                respText,
                sendEmail
            ]);
            if (res && res.success) {
                this.state.reviewsData = res.data;
                if (this.notification) {
                    this.notification.add(res.message, { type: "success" });
                }
                this.closeReviewDetail();
            } else if (res && res.error) {
                if (this.notification) this.notification.add(res.error, { type: "danger" });
            }
        } catch (err) {
            console.error("Failed to acknowledge review:", err);
            if (this.notification) this.notification.add("Failed to acknowledge review.", { type: "danger" });
        } finally {
            this.state.reviewDetailAckSaving = false;
        }
    }

    async deleteReview(review, ev) {
        if (ev) ev.stopPropagation();
        if (!confirm(`Are you sure you want to delete review "${review.name}"?`)) return;
        try {
            const res = await this.orm.call("project.manage", "delete_customer_review_dashboard", [review.id]);
            if (res && res.success) {
                this.state.reviewsData = res.data;
                if (this.notification) {
                    this.notification.add(res.message || "Review deleted.", { type: "info" });
                }
                if (this.state.reviewDetailOpen && this.state.reviewDetailData?.id === review.id) {
                    this.closeReviewDetail();
                }
            } else if (res && res.error) {
                if (this.notification) this.notification.add(res.error, { type: "danger" });
            }
        } catch (err) {
            console.error("Failed to delete review:", err);
            if (this.notification) this.notification.add("Failed to delete review.", { type: "danger" });
        }
    }

    openStandardReviewsView() {
        this.actionService.doAction("project_manage.action_project_manage_review");
    }

    setReviewRatingFilter(rating) {
        this.state.reviewFilterRating = rating;
    }

    setReviewStatusFilter(status) {
        this.state.reviewFilterStatus = status;
    }

    setReviewTypeFilter(type) {
        this.state.reviewFilterType = type;
    }

    setReviewProjectFilter(pId) {
        this.state.reviewProjectFilter = pId;
        this.loadCustomerReviews(pId !== 'all' ? pId : null);
    }

}

registry.category("actions").add("project_manage_dashboard", ProjectManageDashboard);
