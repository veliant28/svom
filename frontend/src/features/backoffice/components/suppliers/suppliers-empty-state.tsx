type Translator = (key: string, values?: Record<string, string | number>) => string;

export function suppliersWorkspaceEmptyLabel(t: Translator): string {
  return t("states.emptyWorkspace");
}

export function suppliersSchedulesEmptyLabel(tCommon: Translator): string {
  return tCommon("importSchedules.states.empty");
}
