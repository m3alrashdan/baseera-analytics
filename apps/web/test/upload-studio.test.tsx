import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { UploadStudio } from "@/components/upload-studio";

describe("UploadStudio", () => {
  it("selects a supported file and submits it through the provided uploader", async () => {
    const upload = vi
      .fn()
      .mockResolvedValue({ dataset_id: "ds_01", status: "accepted" });
    const user = userEvent.setup();
    render(<UploadStudio locale="en" upload={upload} />);
    const file = new File(["id,total\n001,12"], "orders.csv", {
      type: "text/csv",
    });

    await user.upload(screen.getByLabelText(/choose data file/i), file);
    expect(screen.getByText("orders.csv")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /upload and inspect/i }),
    );
    expect(upload).toHaveBeenCalledWith(file);
    expect(await screen.findByRole("status")).toHaveTextContent(/accepted/i);
  });
});
