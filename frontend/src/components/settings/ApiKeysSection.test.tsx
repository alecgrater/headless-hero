import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import api from "../../api";
import ApiKeysSection from "./ApiKeysSection";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("ApiKeysSection", () => {
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
});
