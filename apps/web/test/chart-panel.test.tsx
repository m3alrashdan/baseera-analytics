import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ChartPanel } from "@/components/chart-panel";

it("does not interpolate a line across an unobserved period", () => {
  const { container } = render(
    <ChartPanel
      locale="en"
      title="Revenue"
      data={[
        { label: "Jan", value: 10 },
        { label: "Feb", value: null },
        { label: "Mar", value: 20 },
      ]}
    />,
  );
  const path = container.querySelector("path.chart-line")!.getAttribute("d")!;
  expect(path.match(/M/g)).toHaveLength(2);
  expect(path).not.toContain("L");
});

it("explains absent chart data", () => {
  render(<ChartPanel locale="en" title="Capacity" data={[]} />);
  expect(screen.getByText(/No chart values/)).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
