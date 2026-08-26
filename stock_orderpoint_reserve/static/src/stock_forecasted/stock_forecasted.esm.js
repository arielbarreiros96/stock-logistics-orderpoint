/* Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
   License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

import {StockForecasted} from "@stock/stock_forecasted/stock_forecasted";
import {patch} from "@web/core/utils/patch";

patch(StockForecasted.prototype, {
    /**
     * The graph is a plain view on report.stock.quantity and knows nothing of
     * this module, so the reserve schedule travels to its renderer here.
     */
    get orderpointReserveGraphContext() {
        return {
            fill_temporal: false,
            orderpoint_reserve_schedule:
                this.docs?.orderpoint_reserve?.schedule || false,
        };
    },
});
