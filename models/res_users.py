from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Non-stored compute fallback so PostgreSQL never queries a non-existent column,
    # while satisfying any legacy view parser.
    bfx_max_workload = fields.Float(string='Max Workload', compute='_compute_dummy', store=False)

    def _compute_dummy(self):
        for rec in self:
            rec.bfx_max_workload = 0.0

    def _register_hook(self):
        super()._register_hook()
        try:
            # Automatically deactivate any orphaned views referencing obsolete fields from previous modules
            self.env.cr.execute("""
                UPDATE ir_ui_view
                SET active = false
                WHERE active = true
                  AND arch_db::text LIKE '%bfx_max_workload%';
            """)
        except Exception:
            pass

        try:
            # Clean up leftover activities for removed or uninstalled models
            self.env.cr.execute("""
                DELETE FROM mail_activity
                WHERE res_model IN ('business.project', 'sop.implementation')
                   OR res_model NOT IN (SELECT model FROM ir_model);
            """)
        except Exception:
            pass

        try:
            # Clean up leftover followers for removed or uninstalled models
            self.env.cr.execute("""
                DELETE FROM mail_followers
                WHERE res_model IN ('business.project', 'sop.implementation')
                   OR res_model NOT IN (SELECT model FROM ir_model);
            """)
        except Exception:
            pass

        try:
            # ---- Auto-sync Project Management security groups, privilege and access rights ----
            cat = self.env.ref('project_manage.module_category_project_manage', raise_if_not_found=False)
            priv = self.env.ref('project_manage.res_groups_privilege_project_manage', raise_if_not_found=False)
            admin_grp = self.env.ref('project_manage.group_project_manage_administrator', raise_if_not_found=False)

            # 1. Ensure all 6 groups have privilege_id set in DB
            group_xml_ids = [
                'group_project_manage_consultant',
                'group_project_manage_team_lead',
                'group_project_manage_manager',
                'group_project_manage_vp',
                'group_project_manage_ceo',
                'group_project_manage_administrator',
            ]
            for xml_id in group_xml_ids:
                grp = self.env.ref(f'project_manage.{xml_id}', raise_if_not_found=False)
                if grp:
                    vals = {}
                    if priv and grp.privilege_id != priv:
                        vals['privilege_id'] = priv.id
                    if vals:
                        grp.sudo().write(vals)

            # 2. Unlink base.group_system from group_project_manage_administrator in implied_ids
            # so that System Admins (like Mitchell Admin) are NOT restricted to Administrator only!
            sys_grp = self.env.ref('base.group_system', raise_if_not_found=False)
            if sys_grp and admin_grp:
                self.env.cr.execute("""
                    DELETE FROM res_groups_implied_rel 
                    WHERE gid = %s AND hid = %s
                """, (sys_grp.id, admin_grp.id))

            # 3. Ensure Mitchell Admin (id=2), root (id=1), and any admin users belong to group_project_manage_administrator
            if admin_grp:
                self.env.cr.execute("""
                    INSERT INTO res_groups_users_rel (gid, uid)
                    SELECT %s, u.id
                    FROM res_users u
                    WHERE (u.id IN (1, 2) OR u.id IN (
                        SELECT r2.uid FROM res_groups_users_rel r2
                        JOIN ir_model_data imd ON imd.res_id = r2.gid AND imd.model = 'res.groups'
                        WHERE imd.module = 'base' AND imd.name IN ('group_system', 'group_erp_manager')
                    ))
                      AND NOT EXISTS (
                          SELECT 1 FROM res_groups_users_rel r WHERE r.gid = %s AND r.uid = u.id
                      );
                """, (admin_grp.id, admin_grp.id))

            # 4. Guarantee ir_model_access permissions for project.manage.scope in this database
            scope_model = self.env['ir.model'].search([('model', '=', 'project.manage.scope')], limit=1)
            if scope_model:
                user_grp = self.env.ref('base.group_user', raise_if_not_found=False)
                if user_grp:
                    self.env.cr.execute("""
                        INSERT INTO ir_model_access (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink, active)
                        SELECT 'access_pm_scope_user_auto', %s, %s, true, true, true, false, true
                        WHERE NOT EXISTS (
                            SELECT 1 FROM ir_model_access WHERE model_id = %s AND group_id = %s
                        );
                        UPDATE ir_model_access
                        SET perm_create = true, perm_write = true, perm_read = true
                        WHERE model_id = %s AND group_id = %s;
                    """, (scope_model.id, user_grp.id, scope_model.id, user_grp.id, scope_model.id, user_grp.id))
                if sys_grp:
                    self.env.cr.execute("""
                        INSERT INTO ir_model_access (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink, active)
                        SELECT 'access_pm_scope_sys_auto', %s, %s, true, true, true, true, true
                        WHERE NOT EXISTS (
                            SELECT 1 FROM ir_model_access WHERE model_id = %s AND group_id = %s
                        );
                        UPDATE ir_model_access
                        SET perm_create = true, perm_write = true, perm_read = true, perm_unlink = true
                        WHERE model_id = %s AND group_id = %s;
                    """, (scope_model.id, sys_grp.id, scope_model.id, sys_grp.id, scope_model.id, sys_grp.id))
                if admin_grp:
                    self.env.cr.execute("""
                        INSERT INTO ir_model_access (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink, active)
                        SELECT 'access_pm_scope_admin_auto', %s, %s, true, true, true, true, true
                        WHERE NOT EXISTS (
                            SELECT 1 FROM ir_model_access WHERE model_id = %s AND group_id = %s
                        );
                        UPDATE ir_model_access
                        SET perm_create = true, perm_write = true, perm_read = true, perm_unlink = true
                        WHERE model_id = %s AND group_id = %s;
                    """, (scope_model.id, admin_grp.id, scope_model.id, admin_grp.id, scope_model.id, admin_grp.id))

            # 5. Fix multi-company rule in DB so scopes with project_id = False are always visible
            domain_multi_comp = "['|', ('project_id', '=', False), ('project_id.company_id', 'in', company_ids)]"
            self.env.cr.execute("""
                UPDATE ir_rule
                SET domain_force = %s
                WHERE name = 'Project Scope Multi-Company';
            """, (domain_multi_comp,))

            # 6. Ensure rule_project_scope_exec and rule_project_manage_exec include Manager, VP, CEO, Admin, System
            mgr_grp = self.env.ref('project_manage.group_project_manage_manager', raise_if_not_found=False)
            rule_proj_exec = self.env.ref('project_manage.rule_project_manage_exec', raise_if_not_found=False)
            rule_scope_exec = self.env.ref('project_manage.rule_project_scope_exec', raise_if_not_found=False)
            for rule_rec in (rule_proj_exec, rule_scope_exec):
                if rule_rec:
                    self.env.cr.execute("""
                        UPDATE ir_rule
                        SET domain_force = '[(1, ''='', 1)]'
                        WHERE id = %s;
                    """, (rule_rec.id,))
                    for g in (sys_grp, mgr_grp, admin_grp):
                        if g:
                            self.env.cr.execute("""
                                INSERT INTO rule_group_rel (rule_group_id, group_id)
                                SELECT %s, %s
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM rule_group_rel WHERE rule_group_id = %s AND group_id = %s
                                );
                            """, (rule_rec.id, g.id, rule_rec.id, g.id))

            # Deactivate legacy rule_project_manage_pm if present so manager has full exec access
            rule_pm = self.env.ref('project_manage.rule_project_manage_pm', raise_if_not_found=False)
            if rule_pm:
                self.env.cr.execute("UPDATE ir_rule SET active = false WHERE id = %s;", (rule_pm.id,))

            # 7. Ensure Team Lead and Consultant project & team access rules
            tl_grp = self.env.ref('project_manage.group_project_manage_team_lead', raise_if_not_found=False)
            consultant_grp = self.env.ref('project_manage.group_project_manage_consultant', raise_if_not_found=False)
            rule_proj_tl = self.env.ref('project_manage.rule_project_manage_tl', raise_if_not_found=False)
            if rule_proj_tl:
                domain_tl = "['|', '|', '|', ('team_lead_id.user_id', '=', user.id), ('team_id.team_lead_id', '=', user.id), ('team_id.member_ids', 'in', [user.id]), ('consultant_ids.user_id', '=', user.id)]"
                self.env.cr.execute("UPDATE ir_rule SET domain_force = %s WHERE id = %s;", (domain_tl, rule_proj_tl.id))

            # Ensure project.manage.team rules and model access exist in DB
            team_model = self.env['ir.model'].search([('model', '=', 'project.manage.team')], limit=1)
            if team_model:
                # Guarantee Project Manager can create, write, read and unlink project teams
                if mgr_grp:
                    self.env.cr.execute("""
                        INSERT INTO ir_model_access (name, model_id, group_id, perm_read, perm_write, perm_create, perm_unlink, active)
                        SELECT 'access_pm_team_mgr_auto', %s, %s, true, true, true, true, true
                        WHERE NOT EXISTS (
                            SELECT 1 FROM ir_model_access WHERE model_id = %s AND group_id = %s
                        );
                        UPDATE ir_model_access
                        SET perm_create = true, perm_write = true, perm_read = true, perm_unlink = true
                        WHERE model_id = %s AND group_id = %s;
                    """, (team_model.id, mgr_grp.id, team_model.id, mgr_grp.id, team_model.id, mgr_grp.id))

                # 7a. Team Exec/Manager Rule
                self.env.cr.execute("""
                    INSERT INTO ir_rule (name, model_id, domain_force, active)
                    SELECT 'Executive and Manager Teams Access', %s, '[(1, ''='', 1)]', true
                    WHERE NOT EXISTS (
                        SELECT 1 FROM ir_rule WHERE name = 'Executive and Manager Teams Access' AND model_id = %s
                    );
                """, (team_model.id, team_model.id))
                self.env.cr.execute("SELECT id FROM ir_rule WHERE name = 'Executive and Manager Teams Access' AND model_id = %s LIMIT 1;", (team_model.id,))
                team_exec_row = self.env.cr.fetchone()
                if team_exec_row:
                    team_exec_rule_id = team_exec_row[0]
                    for g in (sys_grp, mgr_grp, admin_grp):
                        if g:
                            self.env.cr.execute("""
                                INSERT INTO rule_group_rel (rule_group_id, group_id)
                                SELECT %s, %s
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM rule_group_rel WHERE rule_group_id = %s AND group_id = %s
                                );
                            """, (team_exec_rule_id, g.id, team_exec_rule_id, g.id))

                # 7b. Team Lead Assigned Team Rule
                if tl_grp:
                    domain_team_tl = "['|', ('team_lead_id', '=', user.id), ('member_ids', 'in', [user.id])]"
                    self.env.cr.execute("""
                        INSERT INTO ir_rule (name, model_id, domain_force, active)
                        SELECT 'Team Lead Assigned Team Access', %s, %s, true
                        WHERE NOT EXISTS (
                            SELECT 1 FROM ir_rule WHERE name = 'Team Lead Assigned Team Access' AND model_id = %s
                        );
                    """, (team_model.id, domain_team_tl, team_model.id))
                    self.env.cr.execute("SELECT id FROM ir_rule WHERE name = 'Team Lead Assigned Team Access' AND model_id = %s LIMIT 1;", (team_model.id,))
                    team_tl_row = self.env.cr.fetchone()
                    if team_tl_row:
                        team_tl_rule_id = team_tl_row[0]
                        self.env.cr.execute("""
                            INSERT INTO rule_group_rel (rule_group_id, group_id)
                            SELECT %s, %s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM rule_group_rel WHERE rule_group_id = %s AND group_id = %s
                            );
                        """, (team_tl_rule_id, tl_grp.id, team_tl_rule_id, tl_grp.id))

                # 7c. Consultant Assigned Team Rule
                if consultant_grp:
                    domain_team_cons = "[('member_ids', 'in', [user.id])]"
                    self.env.cr.execute("""
                        INSERT INTO ir_rule (name, model_id, domain_force, active)
                        SELECT 'Consultant Assigned Team Access', %s, %s, true
                        WHERE NOT EXISTS (
                            SELECT 1 FROM ir_rule WHERE name = 'Consultant Assigned Team Access' AND model_id = %s
                        );
                    """, (team_model.id, domain_team_cons, team_model.id))
                    self.env.cr.execute("SELECT id FROM ir_rule WHERE name = 'Consultant Assigned Team Access' AND model_id = %s LIMIT 1;", (team_model.id,))
                    team_cons_row = self.env.cr.fetchone()
                    if team_cons_row:
                        team_cons_rule_id = team_cons_row[0]
                        self.env.cr.execute("""
                            INSERT INTO rule_group_rel (rule_group_id, group_id)
                            SELECT %s, %s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM rule_group_rel WHERE rule_group_id = %s AND group_id = %s
                            );
                        """, (team_cons_rule_id, consultant_grp.id, team_cons_rule_id, consultant_grp.id))

            # 8. Ensure approval log model access has create/write permissions for all active roles
            log_model = self.env['ir.model'].search([('model', '=', 'project.manage.scope.approval.log')], limit=1)
            if log_model:
                consultant_grp = self.env.ref('project_manage.group_project_manage_consultant', raise_if_not_found=False)
                if consultant_grp:
                    self.env.cr.execute("""
                        UPDATE ir_model_access
                        SET perm_create = true, perm_write = true, perm_read = true
                        WHERE model_id = %s AND group_id = %s;
                    """, (log_model.id, consultant_grp.id))
                user_grp = self.env.ref('base.group_user', raise_if_not_found=False)
                if user_grp:
                    self.env.cr.execute("""
                        UPDATE ir_model_access
                        SET perm_create = true, perm_write = true, perm_read = true
                        WHERE model_id = %s AND group_id = %s;
                    """, (log_model.id, user_grp.id))

            # 8. Sync consultant and team lead rule domains in DB so users see assigned tasks or projects they lead/manage
            domain_consultant = "['|', '|', '|', '|', '|', ('responsible_ids.user_id', '=', user.id), ('responsible_id.user_id', '=', user.id), ('project_id.team_lead_id.user_id', '=', user.id), ('project_id.team_id.team_lead_id', '=', user.id), ('project_id.manager_id.user_id', '=', user.id), ('project_id.consultant_ids.user_id', '=', user.id)]"
            self.env.cr.execute("""
                UPDATE ir_rule
                SET domain_force = %s
                WHERE name = 'Consultant Assigned Tasks';
            """, (domain_consultant,))

            domain_tl_scope = "['|', ('project_id', '=', False), '|', '|', '|', '|', ('project_id.team_lead_id.user_id', '=', user.id), ('project_id.team_id.team_lead_id', '=', user.id), ('project_id.manager_id.user_id', '=', user.id), ('responsible_ids.user_id', '=', user.id), ('responsible_id.user_id', '=', user.id)]"
            self.env.cr.execute("""
                UPDATE ir_rule
                SET domain_force = %s
                WHERE name = 'Team Lead Scopes Access';
            """, (domain_tl_scope,))

            # 8a. Sync existing responsible_id into project_scope_responsible_employee_rel if table exists
            try:
                self.env.cr.execute("""
                    SELECT 1 FROM information_schema.tables WHERE table_name = 'project_scope_responsible_employee_rel';
                """)
                if self.env.cr.fetchone():
                    self.env.cr.execute("""
                        INSERT INTO project_scope_responsible_employee_rel (scope_id, employee_id)
                        SELECT id, responsible_id FROM project_manage_scope
                        WHERE responsible_id IS NOT NULL
                        ON CONFLICT DO NOTHING;
                    """)
            except Exception:
                pass

            # 8b. Ensure any tasks with state 'under_review' are in pending_tl
            self.env.cr.execute("""
                UPDATE project_manage_scope
                SET approval_state = 'pending_tl'
                WHERE state = 'under_review'
                  AND (approval_state IS NULL OR approval_state IN ('draft', 'pending'));
            """)

            # 8c. Ensure all tasks have start_date and end_date populated for calendar view
            self.env.cr.execute("""
                UPDATE project_manage_scope
                SET start_date = COALESCE(end_date, create_date::date, CURRENT_DATE)
                WHERE start_date IS NULL;
                UPDATE project_manage_scope
                SET end_date = COALESCE(start_date, create_date::date, CURRENT_DATE)
                WHERE end_date IS NULL;
            """)

            # 9. Recalculate dynamic metrics (Health, Risk Level, Condition) for existing projects
            all_projects = self.env['project.manage'].search([])
            if all_projects:
                all_projects._compute_metrics()

            # Clear access rule caches so changes take effect immediately
            self.env.registry.clear_cache()
        except Exception:
            pass
