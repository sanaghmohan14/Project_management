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
        this.tableRef = useRef("tableResponsive");

        // Load saved theme or default to light mode
        const savedTheme = localStorage.getItem("pm_dashboard_theme");
        const initialDark = savedTheme ? savedTheme === "dark" : false;

        this.state = useState({
            loading: true,
            darkMode: initialDark,
            selectedTeamId: null,
            activeRoleView: null,
            selectedProjectId: null,
            projectScopesLoading: false,
            projectScopesData: null,
            activeCategoryFilter: 'all',  // 'all', 'documentation', 'implementation'
            activeStatusFilter: 'all',    // 'all', 'completed', 'in_progress', 'pending', 'overdue'
            selectedScopeName: null,      // specific scope filter if clicked
            searchQuery: "",
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
                },
                approvals_summary: {
                    pending_my_approval_count: 0,
                    all_pending_count: 0,
                    pending_items: [],
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
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.setupDraggableTable();
        });
    }

    setupDraggableTable() {
        const slider = this.tableRef.el;
        if (!slider) return;

        let isDown = false;
        let startX = 0;
        let scrollLeft = 0;

        slider.addEventListener("mousedown", (e) => {
            if (e.target.closest("button, a")) return;
            isDown = true;
            slider.classList.add("pm-is-dragging");
            startX = e.pageX - slider.offsetLeft;
            scrollLeft = slider.scrollLeft;
        });

        window.addEventListener("mouseup", () => {
            if (isDown) {
                isDown = false;
                slider.classList.remove("pm-is-dragging");
            }
        });

        slider.addEventListener("mouseleave", () => {
            if (isDown) {
                isDown = false;
                slider.classList.remove("pm-is-dragging");
            }
        });

        slider.addEventListener("mousemove", (e) => {
            if (!isDown) return;
            e.preventDefault();
            const x = e.pageX - slider.offsetLeft;
            const walk = (x - startX) * 1.5;
            slider.scrollLeft = scrollLeft - walk;
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const kwargs = {};
            if (this.state.selectedTeamId) {
                kwargs.team_id = this.state.selectedTeamId;
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
        await this.loadData();
    }

    async onSelectProject(projectId, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        if (this.state.selectedProjectId === projectId) {
            this.state.selectedProjectId = null;
            this.state.projectScopesData = null;
            return;
        }
        this.state.selectedProjectId = projectId;
        this.state.activeCategoryFilter = 'all';
        this.state.activeStatusFilter = 'all';
        this.state.selectedScopeName = null;
        this.state.searchQuery = "";
        await this.loadProjectScopes(projectId);
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
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "project.manage",
            views: [[false, "form"]],
            target: "current",
        });
    }

    createNewTeam() {
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
