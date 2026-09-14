import { describe, expect, it } from "vitest";

import { extractErrorMessage } from "./api";

describe("extractErrorMessage", () => {
  it("returns a plain string detail unchanged", () => {
    expect(extractErrorMessage(400, { detail: "Script not found" })).toBe(
      "Script not found",
    );
  });

  it("flattens a FastAPI validation array instead of returning objects", () => {
    // Rendering this array as a React child crashes the whole app with
    // "Objects are not valid as a React child".
    const detail = [
      {
        type: "string_too_long",
        loc: ["body", "creator_guidance"],
        msg: "String should have at most 2000 characters",
        input: "xxx",
        ctx: { max_length: 2000 },
      },
    ];

    const message = extractErrorMessage(422, { detail });

    expect(typeof message).toBe("string");
    expect(message).toBe(
      "creator_guidance: String should have at most 2000 characters",
    );
  });

  it("joins multiple validation errors", () => {
    const detail = [
      { loc: ["body", "topic"], msg: "Field required" },
      { loc: ["body", "format_id"], msg: "Field required" },
    ];

    expect(extractErrorMessage(422, { detail })).toBe(
      "topic: Field required; format_id: Field required",
    );
  });

  it("falls back to a generic message when detail is an unreadable object", () => {
    expect(extractErrorMessage(422, { detail: { unexpected: true } })).toBe(
      "Invalid request data",
    );
  });

  it("uses status fallbacks when there is no detail", () => {
    expect(extractErrorMessage(404, {})).toBe("Resource not found");
    expect(extractErrorMessage(500, {})).toBe("Server error — please try again");
  });
});
