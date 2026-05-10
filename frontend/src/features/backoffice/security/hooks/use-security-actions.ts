"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";

import { useAuth } from "@/features/auth/hooks/use-auth";
import { useBackofficeFeedback } from "@/features/backoffice/hooks/use-backoffice-feedback";
import { BACKOFFICE_CAPABILITIES, hasBackofficeCapability } from "@/features/backoffice/lib/capabilities";
import {
  addSecurityComment,
  createSecurityBlock,
  extendSecurityBlock,
  markSecurityActorFalsePositive,
  releaseSecurityBlock,
  unwhitelistSecurityActor,
  whitelistSecurityBlock,
} from "@/features/backoffice/security/api/security-api";
import type { SecurityActor, SecurityBlock } from "@/features/backoffice/security/types/security.types";

export function useSecurityActions(onAfterAction: () => void) {
  const { token, user } = useAuth();
  const feedback = useBackofficeFeedback();
  const t = useTranslations("backoffice.security");
  const [submitting, setSubmitting] = useState(false);
  const canRespond = hasBackofficeCapability(user, BACKOFFICE_CAPABILITIES.securityRespond);

  const release = useCallback(async (block: SecurityBlock, reason: string) => {
    if (!token || !canRespond) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }
    setSubmitting(true);
    try {
      await releaseSecurityBlock(token, block.id, reason);
      feedback.showSuccess(t("toasts.releaseSuccess"));
      onAfterAction();
    } catch (error) {
      feedback.showApiError(error, t("errors.releaseFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [canRespond, feedback, onAfterAction, t, token]);

  const whitelist = useCallback(async (actor: SecurityActor, reason: string) => {
    if (!canRespond) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }
    if (!token) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }

    if (actor.status === "whitelisted") {
      setSubmitting(true);
      try {
        await unwhitelistSecurityActor(token, actor.id, reason);
        feedback.showSuccess(t("toasts.unwhitelistSuccess"));
        onAfterAction();
      } catch (error) {
        feedback.showApiError(error, t("errors.unwhitelistFailed"));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!actor.active_block) {
      feedback.showWarning(t("errors.noActiveBlock"));
      return;
    }
    setSubmitting(true);
    try {
      await whitelistSecurityBlock(token, actor.active_block.id, reason);
      feedback.showSuccess(t("toasts.whitelistSuccess"));
      onAfterAction();
    } catch (error) {
      feedback.showApiError(error, t("errors.whitelistFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [canRespond, feedback, onAfterAction, t, token]);

  const extend = useCallback(async (actor: SecurityActor, minutes: number, reason: string) => {
    if (!canRespond) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }
    if (!token || !actor.active_block) {
      feedback.showWarning(t("errors.noActiveBlock"));
      return;
    }
    setSubmitting(true);
    try {
      await extendSecurityBlock(token, actor.active_block.id, minutes, reason);
      feedback.showSuccess(t("toasts.extendSuccess"));
      onAfterAction();
    } catch (error) {
      feedback.showApiError(error, t("errors.extendFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [canRespond, feedback, onAfterAction, t, token]);

  const comment = useCallback(async (actor: SecurityActor, value: string) => {
    if (!token || !canRespond) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }
    setSubmitting(true);
    try {
      await addSecurityComment(token, actor.id, value);
      feedback.showSuccess(t("toasts.commentSuccess"));
      onAfterAction();
    } catch (error) {
      feedback.showApiError(error, t("errors.commentFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [canRespond, feedback, onAfterAction, t, token]);

  const reblock = useCallback(async (actor: SecurityActor, reason: string) => {
    if (!token || !canRespond) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }
    setSubmitting(true);
    try {
      await createSecurityBlock(token, actor.id, reason);
      feedback.showSuccess(t("toasts.reblockSuccess"));
      onAfterAction();
    } catch (error) {
      feedback.showApiError(error, t("errors.reblockFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [canRespond, feedback, onAfterAction, t, token]);

  const falsePositive = useCallback(async (actor: SecurityActor, reason: string) => {
    if (!token || !canRespond) {
      feedback.showWarning(t("errors.respondPermission"));
      return;
    }
    setSubmitting(true);
    try {
      await markSecurityActorFalsePositive(token, actor.id, reason);
      feedback.showSuccess(t("toasts.falsePositiveSuccess"));
      onAfterAction();
    } catch (error) {
      feedback.showApiError(error, t("errors.falsePositiveFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [canRespond, feedback, onAfterAction, t, token]);

  const copyIp = useCallback(async (actor: SecurityActor) => {
    try {
      await navigator.clipboard.writeText(actor.source_ip || actor.source_identifier);
      feedback.showSuccess(t("toasts.copySuccess"));
    } catch (error) {
      feedback.showApiError(error, t("errors.copyFailed"));
    }
  }, [feedback, t]);

  return { submitting, release, whitelist, extend, comment, reblock, falsePositive, copyIp };
}
