"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import Modal from "@/components/Modal";
import TextField from "@/components/TextField";
import { useToast } from "@/components/ToastProvider";

import { deleteAccount } from "./deleteAccount";

/**
 * "Delete account" at the bottom of Settings. Asks for the password before
 * anything is deleted; deleteAccount.ts does the three steps.
 */
export default function DeleteAccountCard() {
  const router = useRouter();
  const showToast = useToast();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    if (working) return; // Don't hide the dialog halfway through.
    setOpen(false);
    setPassword("");
    setError(null);
  }

  async function confirm(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!password) return;
    setWorking(true);
    setError(null);
    try {
      await deleteAccount(password);
      showToast({ tone: "success", title: "Your account was deleted" });
      router.push("/");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Something went wrong. Please try again.");
      setWorking(false);
    }
  }

  return (
    <>
      <section className="flex w-full flex-col gap-3 rounded-[14px] border border-border bg-surface px-[18px] py-[14px]">
        <h2 className="text-[15px] font-bold tracking-[-0.3px] text-foreground">Delete account</h2>
        <p className="text-sm leading-5 text-muted">
          Deletes your account, your Personal workspace and everything in it. If you own an
          organization, delete it first. This can&apos;t be undone.
        </p>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex h-[48px] w-full items-center justify-center rounded-[10px] border border-danger bg-surface text-[15px] font-bold text-danger md:w-fit md:px-6"
        >
          Delete account
        </button>
      </section>

      <Modal
        open={open}
        onClose={close}
        title="Delete your account?"
        actions={
          <>
            <Button variant="secondary" onClick={close} disabled={working}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => confirm()} disabled={working || !password}>
              {working ? "Deleting…" : "Delete account"}
            </Button>
          </>
        }
      >
        <p>
          Your Personal workspace, its assets and receipts, and your notifications are deleted. Assets
          in other organizations stay there, unassigned. You can sign up again later with the same email.
        </p>
        <form onSubmit={confirm} className="mt-4">
          <TextField
            id="delete-account-password"
            label="Enter your password to confirm"
            iconSrc="/icons/lock.svg"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={working}
          />
        </form>
        {error && (
          <p role="alert" className="mt-3 rounded-[10px] bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {error}
          </p>
        )}
      </Modal>
    </>
  );
}
