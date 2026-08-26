import {registry} from "@web/core/registry";

// The canvas is in the page a beat before Chart.js owns it.
async function getReserveLine(canvas) {
    for (let attempt = 0; attempt < 50; attempt++) {
        const chart = window.Chart?.getChart(canvas);
        const dataset = chart?.data?.datasets?.find(
            (item) => item.label === "Available to Replenish"
        );
        if (dataset) {
            return {chart, dataset};
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error("the reserve line is missing from the graph");
}

registry.category("web_tour.tours").add("stock_orderpoint_reserve_forecast", {
    steps: () => [
        {
            content: "Open the product the reserve is set on",
            trigger: ".o_kanban_record:contains(Reserve Tour Product)",
            run: "click",
        },
        {
            content: "Open its Forecasted Report",
            trigger: "button[name=action_product_tmpl_forecast_report]",
            run: "click",
        },
        {
            content: "The reserve line names the location it applies to",
            // Not the warehouse code: it differs between databases.
            trigger: ".o_orderpoint_reserve h6:contains(/Stock)",
        },
        {
            content: "On hand, less committed, less the reserve",
            trigger:
                ".o_orderpoint_reserve div[name=orderpoint_reserve_available]:contains(30.00)",
        },
        {
            content: "The graph steps up on the day the reserve lifts",
            trigger: ".o_stock_forecasted_page canvas",
            async run() {
                const {chart, dataset} = await getReserveLine(this.anchor);
                const gaps = dataset.data.filter(
                    (value) => value === null || value === undefined
                ).length;
                if (gaps || dataset.data.length !== chart.data.labels.length) {
                    throw new Error(
                        `expected ${chart.data.labels.length} points with no gaps, ` +
                            `got ${dataset.data.length} with ${gaps} gaps`
                    );
                }
                // The y axis is stacked for line charts, so sharing the
                // forecast's stack would draw this line at forecast + reserve.
                if (
                    chart.options.scales?.y?.stacked &&
                    dataset.stack === chart.data.datasets[0].stack
                ) {
                    throw new Error(
                        "the reserve line shares the forecast's stack and would " +
                            "be drawn at the sum of the two"
                    );
                }
                // 100 on hand, 40 committed, 30 reserved until it lifts, and 0
                // over the history the graph draws.
                const values = [...new Set(dataset.data)].sort((a, b) => a - b);
                if (values.length !== 3 || values.join() !== "0,30,60") {
                    throw new Error(
                        `expected the line to read 0 then 30 then 60, got ${values}`
                    );
                }
            },
        },
    ],
});
