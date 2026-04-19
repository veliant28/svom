import { useEffect, useRef } from "react";

export function CategoryDeleteModal({
  isOpen,
  message,
  onConfirm,
  onClose,
}: {
  isOpen: boolean;
  message: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const wasOpenRef = useRef(false);

  useEffect(() => {
    if (!isOpen) {
      wasOpenRef.current = false;
      return;
    }

    if (wasOpenRef.current) {
      return;
    }
    wasOpenRef.current = true;

    const confirmed = window.confirm(message);
    if (confirmed) {
      onConfirm();
      return;
    }
    onClose();
  }, [isOpen, message, onClose, onConfirm]);

  return null;
}
