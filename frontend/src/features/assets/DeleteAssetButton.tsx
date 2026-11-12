"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/Button";
import Modal from "@/components/Modal";
import { useToast } from "@/components/ToastProvider";
import { canManageAssets, useWorkspaceRole } from "@/features/workspace/WorkspaceRole";

import { deleteAsset } from "./deleteAsset";

/**
 * "Delete Asset" on Asset Detail (#59). Owners and admins only; asks first,
 * because the backend deletes for good. On success: a toast, then back to the
 * Assets list (the toast survives the page change, see ToastProvider).
 */
export default function DeleteAssetButton({ assetId, assetName }: { assetId: string; assetName: string }) {
  const role = useWorkspaceRole();
  const router = useRouter();
  const showToast = useToast();
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hooks first, then the early return: React needs the same hooks on every render.
  if (!canManageAssets(role)) return null;

  function close() {
    if (deleting) return; // Don't hide the dialog halfway through a request.
    setOpen(false);
    setError(null);
  }

  async function confirmDelete() {
    setDeleting(true);
    setError(null);
    try {
      await deleteAsset(assetId);
      showToast({ tone: "success", title: "Asset deleted", message: `${assetName} was removed.` });
      router.push("/assets");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Couldn't delete the asset.");
      setDeleting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-[54px] w-full items-center justify-center rounded-[10px] border border-danger bg-surface text-base font-bold tracking-[-0.32px] text-danger"
      >
        Delete Asset
      </button>

      <Modal
        open={open}
        onClose={close}
        title="Delete this asset?"
        actions={
          <>
            <Button variant="secondary" onClick={close} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} disabled={deleting}>
              {deleting ? "Deleting…" : "Delete"}
            </Button>
          </>
        }
      >
        <p>
          {assetName}, its warranty and its linked documents will be removed for good. This can&apos;t be
          undone.
        </p>
        {error && (
          <p role="alert" className="mt-3 rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {error}
          </p>
        )}
      </Modal>
    </>
  );
}
