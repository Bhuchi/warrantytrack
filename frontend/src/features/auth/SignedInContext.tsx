"use client";

import { createContext, useContext } from "react";

export const SignedInNameContext = createContext<string | null>(null);
export function useSignedInName() { return useContext(SignedInNameContext); }
