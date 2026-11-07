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

            # 3. Ensure Mitchell Admin (id=2) and root (id=1) belong to group_project_manage_administrator
            if admin_grp:
                self.env.cr.execute("""
                    INSERT INTO res_groups_users_rel (gid, uid)
                    SELECT %s, u.id
                    FROM res_users u
                    WHERE u.id IN (1, 2)
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

            # 6. Ensure rule_project_scope_exec includes base.group_system in DB
            if sys_grp:
                rule_scope_exec = self.env.ref('project_manage.rule_project_scope_exec', raise_if_not_found=False)
                if rule_scope_exec:
                    self.env.cr.execute("""
                        INSERT INTO rule_group_rel (rule_group_id, group_id)
                        SELECT %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM rule_group_rel WHERE rule_group_id = %s AND group_id = %s
                        );
                    """, (rule_scope_exec.id, sys_grp.id, rule_scope_exec.id, sys_grp.id))

            # Clear access rule caches so changes take effect immediately
            self.env.registry.clear_cache()
        except Exception:
            pass
