/* Copyright 2026 Ariel Barreiros (https://github.com/arielbarreiros96)
   License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */

import {ForecastedHeader} from "@stock/stock_forecasted/forecasted_header";
import {patch} from "@web/core/utils/patch";

patch(ForecastedHeader.prototype, {
    get orderpointReserve() {
        return this.props.docs.orderpoint_reserve;
    },
});
