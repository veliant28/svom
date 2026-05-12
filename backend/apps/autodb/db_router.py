class AutoDbRouter:
    route_app_labels = {"autodb"}
    db_alias = "auto_db_pro"
    state_db_alias = "default"
    state_model_names = {
        "autodbmatchevidence",
        "autodbmatchingrun",
        "autodbmatchjob",
        "autodbremotequotastate",
    }

    def _is_state_model(self, model) -> bool:
        return (
            model._meta.app_label in self.route_app_labels
            and model._meta.model_name in self.state_model_names
        )

    def _is_state_model_name(self, model_name: str | None) -> bool:
        return str(model_name or "").lower() in self.state_model_names

    def db_for_read(self, model, **hints):
        if self._is_state_model(model):
            return self.state_db_alias
        if model._meta.app_label in self.route_app_labels:
            return self.db_alias
        return None

    def db_for_write(self, model, **hints):
        if self._is_state_model(model):
            return self.state_db_alias
        if model._meta.app_label in self.route_app_labels:
            return self.db_alias
        return None

    def allow_relation(self, obj1, obj2, **hints):
        app1 = obj1._meta.app_label
        app2 = obj2._meta.app_label
        state1 = self._is_state_model(obj1)
        state2 = self._is_state_model(obj2)
        if state1 or state2:
            if app1 in self.route_app_labels and app2 in self.route_app_labels and state1 != state2:
                return False
            return None
        if app1 in self.route_app_labels or app2 in self.route_app_labels:
            return app1 in self.route_app_labels and app2 in self.route_app_labels
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            if self._is_state_model_name(model_name):
                return db == self.state_db_alias
            if model_name is None:
                return db in {self.db_alias, self.state_db_alias}
            return db == self.db_alias
        if db == self.db_alias:
            return False
        return None
