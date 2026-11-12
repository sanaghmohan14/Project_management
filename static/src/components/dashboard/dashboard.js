/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

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

        this.state = useState({
            loading: true,
            darkMode: initialDark,
            activeMainView: 'dashboard',  // 'dashboard' or 'calendar'
            calendarTimeFilter: 'month',  // 'today', 'tomorrow', 'week', 'month', 'all'
            calendarViewMode: 'month',   // 'month', 'week', 'agenda'
            calendarCategoryFilter: 'all', // 'all', 'documentation', 'implementation'
            calendarTypeFilter: 'task',  // strictly tasks only
            calendarStatusFilter: 'all', // 'all', 'overdue', 'in_progress', 'done'
            calendarYear: new Date().getFullYear(),
            calendarMonth: new Date().getMonth(), // 0-11
            calendarDate: new Date().getDate(),
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
            bulkWizardOpen: false,
            bulkData: {
                target: 'scope',
                scope_name_filter: '',
                responsible_id: '',
                start_date: '',
                end_date: '',
                state: '',
                category: '',
            },
            savingScope: false,
            taskTab: 'pending', // 'pending', 'completed', 'overdue', 'waiting_approval', 'all'
            taskCategoryFilter: 'all', // 'all', 'documentation', 'implementation'
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
            },
        });

        onWillStart(async () => {
            await this.loadData();
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
        this.state.taskConsultantFilter = 'all';
        this.state.taskProjectFilter = 'all';
        this.state.taskSearchQuery = '';
    }

    scrollToTasksHub() {
        if (typeof document !== 'undefined') {
            const el = document.getElementById("pm-tasks-hub");
            if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
                return;
            }
        }
        this.viewMyTasks();
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

        // 3. Consultant Filter
        if (this.state.taskConsultantFilter && this.state.taskConsultantFilter !== 'all') {
            list = list.filter(t => String(t.responsible_id) === String(this.state.taskConsultantFilter));
        }

        // 4. Project Filter
        if (this.state.taskProjectFilter && this.state.taskProjectFilter !== 'all') {
            list = list.filter(t => String(t.project_id) === String(this.state.taskProjectFilter));
        }

        // 5. Search Query
        if (this.state.taskSearchQuery) {
            const q = this.state.taskSearchQuery;
            list = list.filter(t =>
                (t.name && t.name.toLowerCase().includes(q)) ||
                (t.code && t.code.toLowerCase().includes(q)) ||
                (t.project_name && t.project_name.toLowerCase().includes(q)) ||
                (t.responsible_name && t.responsible_name.toLowerCase().includes(q))
            );
        }

        return list;
    }

    // ==================== CALENDAR VIEW METHODS & GETTERS ====================
    setMainView(view) {
        this.state.activeMainView = view;
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
        if (this.state.calendarViewMode === 'month') {
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
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate - 1);
            this.state.calendarYear = cur.getFullYear();
            this.state.calendarMonth = cur.getMonth();
            this.state.calendarDate = cur.getDate();
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
        } else if (this.state.calendarViewMode === 'week') {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate + 7);
            this.state.calendarYear = cur.getFullYear();
            this.state.calendarMonth = cur.getMonth();
            this.state.calendarDate = cur.getDate();
        } else {
            const cur = new Date(this.state.calendarYear, this.state.calendarMonth, this.state.calendarDate + 1);
            this.state.calendarYear = cur.getFullYear();
            this.state.calendarMonth = cur.getMonth();
            this.state.calendarDate = cur.getDate();
        }
    }

    calendarToday() {
        const now = new Date();
        this.state.calendarYear = now.getFullYear();
        this.state.calendarMonth = now.getMonth();
        this.state.calendarDate = now.getDate();
        this.state.calendarTimeFilter = 'today';
    }

    openCalendarItem(item, ev) {
        if (ev) ev.stopPropagation();
        if (item.type === 'project' && item.record_id) {
            this.openProject(item.record_id);
        } else if (item.type === 'task' && item.record_id) {
            this.openScopeForm(item.record_id, ev);
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
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope",
            res_id: scopeId,
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
        if (item) {
            this.state.wizardData = {
                id: item.id,
                scope: item.scope || item.scope_name || '',
                category: item.category || 'Documentation',
                name: item.name || '',
                item_type: item.item_type || '',
                priority: item.priority ? String(item.priority) : '0',
                responsible_id: item.responsible_id ? String(item.responsible_id) : '',
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
                responsible_id: '',
                start_date: '',
                end_date: '',
                state: 'todo',
            };
        }
        this.state.scopeWizardOpen = true;
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
            const vals = {
                scope: this.state.wizardData.scope,
                category: this.state.wizardData.category,
                name: this.state.wizardData.name,
                item_type: this.state.wizardData.item_type,
                priority: this.state.wizardData.priority || '0',
                responsible_id: this.state.wizardData.responsible_id,
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
                    this.notification.add(this.state.wizardData.id ? "Scope task saved!" : "New scope task created!", { type: "success" });
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

    async applyBulkFill() {
        if (this.state.savingScope) return;
        const projectId = this.state.projectScopesData.project.id;
        const vals = {};
        if (this.state.bulkData.target === 'scope' && this.state.bulkData.scope_name_filter) {
            vals.scope_name_filter = this.state.bulkData.scope_name_filter;
        }
        if (this.state.bulkData.responsible_id) {
            vals.responsible_id = this.state.bulkData.responsible_id;
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

        if (!vals.responsible_id && !vals.start_date && !vals.end_date && !vals.state && !vals.category) {
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
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.scope.import.wizard",
            views: [[false, "form"]],
            target: "new",
            context: { default_project_id: projectId },
        }, {
            onClose: () => {
                if (this.state.selectedProjectId) {
                    this.loadProjectScopes(this.state.selectedProjectId);
                }
                this.loadData();
            }
        });
    }

    async openClientUpdateWizard(projectId, ev) {
        if (ev) ev.stopPropagation();
        if (!projectId) return;
        try {
            const action = await this.orm.call("project.manage", "action_open_client_update_wizard", [projectId]);
            if (action) {
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
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openTeam(teamId) {
        if (!teamId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.team",
            res_id: teamId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createNewProject() {
        if (!this.state.data.user_info.can_create_project) {
            if (this.notification) {
                this.notification.add("Team Leads cannot create projects. Only Project Managers, VP, CEO, and Administrators have project creation access.", { type: "warning" });
            }
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage",
            views: [[false, "form"]],
            target: "current",
        });
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

    viewAllProjects() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            target: "current",
        });
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

    openScope(scopeId) {
        if (!scopeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope",
            res_id: scopeId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    viewAllApprovals() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope",
            name: "Approval Requests",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["approval_state", "in", ["pending_tl", "pending_pm", "pending_vp", "pending_ceo"]]],
            context: { search_default_filter_waiting_my_approval: 1 },
            target: "current",
        });
    }

    viewMyTasks() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage.scope",
            name: "My Assigned Tasks",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: [["is_my_task", "=", true]],
            target: "current",
        });
    }

    async refresh() {
        await this.loadData();
        if (this.notification) {
            this.notification.add("Dashboard refreshed", { type: "success" });
        }
    }
}

registry.category("actions").add("project_manage_dashboard", ProjectManageDashboard);
