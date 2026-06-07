import { render, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { useDebouncedAutosave } from "./useDebouncedAutosave";

function AutosaveHarness({
  enabled,
  save,
}: {
  enabled: boolean;
  save: () => Promise<boolean>;
}) {
  const [tick, setTick] = useState(0);
  useDebouncedAutosave(enabled, save, [tick], 1);
  return (
    <button type="button" onClick={() => setTick((value) => value + 1)}>
      change
    </button>
  );
}

describe("useDebouncedAutosave", () => {
  it("does not mark a dependency set saved when the save fails", async () => {
    const save = vi.fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true);

    const { rerender } = render(<AutosaveHarness enabled save={save} />);

    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));

    rerender(<AutosaveHarness enabled={false} save={save} />);
    rerender(<AutosaveHarness enabled save={save} />);

    await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  });
});
