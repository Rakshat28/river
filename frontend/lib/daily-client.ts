export interface DailySessionResponse {
  room_url: string;
  token: string;
}

export async function createDailySession(): Promise<DailySessionResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";

  const response = await fetch(`${baseUrl}/api/session`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Failed to create Daily session");
  }

  return (await response.json()) as DailySessionResponse;
}
