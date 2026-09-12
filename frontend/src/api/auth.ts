import { apiClient } from "@/api/client";
import type { User } from "@/types";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export async function loginWithGoogle(idToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/google", {
    id_token: idToken,
  });
  return data;
}

export async function fetchCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me");
  return data;
}
