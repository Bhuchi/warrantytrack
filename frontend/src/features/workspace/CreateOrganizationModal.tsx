"use client";

import { useState, type FormEvent } from "react";

import Button from "@/components/Button";
import Modal from "@/components/Modal";

import { createWorkspace, type CreatedWorkspace } from "./createWorkspace";

interface CreateOrganizationModalProps {
  open: boolean;
  onClose: () => void;
  /** Runs once the organization exists, with what the API returned. */
  onCreated: (workspace: CreatedWorkspace) => void;
}

/** Same look as the Add Asset inputs (add-asset/Field.tsx). */
const inputClasses =
  "h-12 w-full rounded-[9px] border border-border bg-surface px-3.5 text-[14px] font-medium tracking-[-0.28px] text-foreground outline-none placeholder:text-muted-light focus:border-brand md:h-[46px]";

/**
 * "Create an organization" — Figma 3640:95 (desktop) and 3640:414 (mobile).
 * One required field, the organization name. CLOUDAPPG5-132.
 *
 * The Create button sits in the modal's actions row, outside the <form>, so
 * it points at the form with `form="create-organization"`. That keeps Enter
 * in the input and a click on Create doing the same thing.
 */
export default function CreateOrganizationModal({ open, onClose, onCreated }: CreateOrganizationModalProps) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmed = name.trim();

  function close() {
    if (saving) return;
    setName("");
    setError(null);
    onClose();
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmed || saving) return;

    setSaving(true);
    setError(null);
    try {
      const workspace = await createWorkspace(trimmed);
      onCreated(workspace);
    } catch {
      setError("Could not create the organization. Please try again.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Create an organization"
      actions={
        <>
          <Button variant="secondary" onClick={close} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="create-organization" disabled={!trimmed || saving}>
            {saving ? "Creating…" : "Create"}
          </Button>
        </>
      }
    >
      <p>You&apos;ll be its owner, and you can invite your team once it&apos;s created.</p>

      <form id="create-organization" onSubmit={handleSubmit} className="mt-4 flex flex-col gap-[7px]">
        <label htmlFor="organization-name" className="text-[12px] font-semibold tracking-[-0.24px] text-foreground">
          Organization name *
        </label>
        <input
          id="organization-name"
          className={inputClasses}
          placeholder="e.g. SIIT Organization"
          autoComplete="organization"
          maxLength={100}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {error && <p className="text-[12px] text-danger">{error}</p>}
      </form>
    </Modal>
  );
}
