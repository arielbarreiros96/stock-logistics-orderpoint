/* Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
   License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

import {StockForecastedGraphRenderer} from "@stock/stock_forecasted/forecasted_graph";
import {_t} from "@web/core/l10n/translation";
import {cookie} from "@web/core/browser/cookie";
import {getCustomColor} from "@web/core/colors/colors";
import {patch} from "@web/core/utils/patch";

patch(StockForecastedGraphRenderer.prototype, {
    /**
     * Draw what automatic replenishment may take, alongside the forecast.
     *
     * Kept out of `this.model.data`, the way core keeps its own overlay out of
     * it. That object survives re-renders, so appending to it stacks a fresh
     * copy of the line on every repaint, and core's pass that blanks repeated
     * points then chews holes in them.
     */
    getLineChartData() {
        const data = super.getLineChartData();
        const schedule = this.model.metaData.context?.orderpoint_reserve_schedule;
        const dates = schedule?.length ? this.getOrderpointReserveDates(data) : null;
        this.orderpointReserveDataset = null;
        if (!dates) {
            return data;
        }
        const color = getCustomColor(cookie.get("color_scheme"), "#343a40", "#e9ecef");
        this.orderpointReserveDataset = {
            label: _t("Available to Replenish"),
            data: dates.map((date) => this.getOrderpointReserveValue(schedule, date)),
            trueLabels: data.datasets[0].trueLabels,
            domains: dates.map(() => []),
            // A stack of its own. The y axis is stacked for line charts
            // (`getScaleOptions`), so sharing the forecast's stack would draw
            // this line at forecast + reserve instead of at its own value.
            stack: "orderpoint_reserve",
            stepped: true,
            spanGaps: false,
            fill: false,
            tension: 0,
            // Dashed, thicker, and appended last so it is drawn last: where
            // the two lines sit on the same value the dashes stay legible and
            // the forecast shows through the gaps.
            borderDash: [8, 6],
            borderCapStyle: "butt",
            borderColor: color,
            borderWidth: 3,
            backgroundColor: color,
            pointRadius: 0,
            pointHitRadius: 20,
            pointHoverRadius: 6,
            pointBackgroundColor: color,
            hoverBackgroundColor: color,
        };
        return {...data, datasets: [...data.datasets, this.orderpointReserveDataset]};
    },

    /** Tooltips read the model, which the line above deliberately stays out of. */
    getTooltipItems(data, metaData, tooltipModel) {
        if (!this.orderpointReserveDataset) {
            return super.getTooltipItems(data, metaData, tooltipModel);
        }
        return super.getTooltipItems(
            {...data, datasets: [...data.datasets, this.orderpointReserveDataset]},
            metaData,
            tooltipModel
        );
    },

    /**
     * The date behind every point of the chart, read off the group domains.
     *
     * All or nothing: a single point this module cannot place would leave a
     * hole in a line whose whole job is to be read across time, so anything
     * other than the plain day by day chart gives up and draws nothing.
     */
    getOrderpointReserveDates(data) {
        const reference = data.datasets[0];
        if (!reference?.domains || reference.domains.length !== reference.data.length) {
            return null;
        }
        const dates = reference.domains.map((domain) => {
            const leaf = (domain || []).find(
                (item) => Array.isArray(item) && item[0] === "date" && item[1] === ">="
            );
            return typeof leaf?.[2] === "string" ? leaf[2].slice(0, 10) : null;
        });
        return dates.every((date) => date) ? dates : null;
    },

    /**
     * What the schedule says is available on a given day, 0 before it starts.
     *
     * The schedule starts today, and there is nothing truthful to say about
     * what could have been replenished last month, so the line stays on the
     * floor over the history -- the same thing the forecast does there.
     */
    getOrderpointReserveValue(schedule, date) {
        let value = 0;
        for (const [start, quantity] of schedule) {
            if (start > date) {
                break;
            }
            value = quantity;
        }
        return value;
    },
});
