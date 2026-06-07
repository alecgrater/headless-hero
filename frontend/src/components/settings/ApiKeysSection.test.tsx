import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../api";
import ApiKeysSection from "./ApiKeysSection";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("ApiKeysSection", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({ ok: true, status: 200, data: {} });
    vi.mocked(api.put).mockClear();
  });

  it("shows GitHub Contents Token under Discovery", async () => {
    vi.mocked(api.get).mockResolvedValue({
      ok: true,
      status: 200,
      data: {
        GITHUB_CONTENTS_TOKEN: {
          configured: false,
          masked: "",
          source: "none",
        },
      },
    });

    render(<ApiKeysSection />);

    expect(await screen.findByText("GitHub Contents Token")).toBeInTheDocument();
    expect(screen.getByText("Fine-grained GitHub token with Contents write access for uploading the sanitized discovery seed.")).toBeInTheDocument();
  });

  it("autosaves entered keys on blur without a save button", async () => {
    render(<ApiKeysSection />);

    const openAiInput = await screen.findByPlaceholderText("sk-...");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();

    fireEvent.change(openAiInput, { target: { value: " sk-test-value " } });
    await new Promise((resolve) => window.setTimeout(resolve, 700));
    expect(api.put).not.toHaveBeenCalled();
    fireEvent.blur(openAiInput);

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/api/settings/keys", {
        OPENAI_API_KEY: "sk-test-value",
      });
    });
  });

  it("autosaves entered keys when Enter commits the field", async () => {
    render(<ApiKeysSection />);

    const openAiInput = await screen.findByPlaceholderText("sk-...");
    fireEvent.change(openAiInput, { target: { value: "sk-enter-value" } });
    fireEvent.keyDown(openAiInput, { key: "Enter" });

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/api/settings/keys", {
        OPENAI_API_KEY: "sk-enter-value",
      });
    });
  });
});
