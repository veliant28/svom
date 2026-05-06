class AutoDbRouter:
    route_app_labels = {"autodb"}
    db_alias = "auto_db_pro"

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.db_alias
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return self.db_alias
        return None

    def allow_relation(self, obj1, obj2, **hints):
        app1 = obj1._meta.app_label
        app2 = obj2._meta.app_label
        if app1 in self.route_app_labels or app2 in self.route_app_labels:
            return app1 in self.route_app_labels and app2 in self.route_app_labels
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.route_app_labels:
            return db == self.db_alias
        if db == self.db_alias:
            return False
        return None
