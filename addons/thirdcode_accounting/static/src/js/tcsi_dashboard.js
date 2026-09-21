/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


class TCSIDashboard extends Component {
    static template = "thirdcode_accounting.TCSIDashboard";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.state = useState({
            loading: true,
            error: false,
            data: null,
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.error = false;
        try {
            this.state.data = await rpc("/thirdcode_accounting/dashboard", {});
        } catch (error) {
            console.error("TCSI dashboard failed to load", error);
            this.state.error = true;
        } finally {
            this.state.loading = false;
        }
    }

    formatMoney(value) {
        const currency = this.state.data?.currency || "USD";
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency,
            maximumFractionDigits: 0,
        }).format(Number(value || 0));
    }

    formatDate(value) {
        if (!value) {
            return "No due date";
        }
        return new Intl.DateTimeFormat(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
        }).format(new Date(`${value}T00:00:00`));
    }

    chartHeight(value) {
        const points = this.state.data?.monthly_activity || [];
        const max = Math.max(
            1,
            ...points.flatMap((point) => [Number(point.sales || 0), Number(point.costs || 0)])
        );
        return Math.max(value ? 9 : 2, Math.round((Number(value || 0) / max) * 100));
    }

    async openNewDocument(moveType) {
        if (!this.state.data?.can_create) {
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: moveType === "out_invoice" ? "New customer invoice" : "New supplier bill",
            res_model: "account.move",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_move_type: moveType,
                default_journal_type: moveType === "out_invoice" ? "sale" : "purchase",
            },
        });
    }

    async openModel(model, actionName, domain = []) {
        if (actionName) {
            await this.action.doAction(actionName);
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    async openRecord(recordId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "account.move",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}


registry.category("actions").add("tcsi_dashboard", TCSIDashboard);
