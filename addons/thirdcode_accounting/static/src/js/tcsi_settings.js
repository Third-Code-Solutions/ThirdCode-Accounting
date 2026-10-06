/** @odoo-module **/
import { onMounted, onWillUnmount, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { SettingsPage } from "@web/webclient/settings_form_view/settings/settings_page";

let pageSequence = 0;
let sectionSequence = 0;

// Read native headings after Odoo applies its search and visibility modifiers.
// Fields, setting blocks, validation and save/discard remain owned by Odoo.
export function visibleSettingsSections(root, prefix) {
    return [...root.querySelectorAll(".app_settings_block h2")]
        .filter(heading => heading.getClientRects().length && !heading.closest(".d-none"))
        .map(heading => {
            if (!heading.id) heading.id = `${prefix}-${++sectionSequence}`;
            if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
            return { id: heading.id, label: heading.textContent.trim(), heading };
        });
}

patch(SettingsPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.tcsiOutline = useState({ sections: [], active: "" });
        this.tcsiHeadingPrefix = `tcsi-settings-section-${++pageSequence}`;
        this.tcsiTargets = new Map();
        onMounted(() => {
            const root = this.settingsRef.el;
            if (!root) return;
            this.tcsiSyncSections();
            this.tcsiOnScroll = () => this.tcsiSyncActiveSection();
            root.addEventListener("scroll", this.tcsiOnScroll, { passive: true });
            this.tcsiObserver = new MutationObserver(() => {
                if (this.tcsiFrame) return;
                this.tcsiFrame = requestAnimationFrame(() => {
                    this.tcsiFrame = 0;
                    this.tcsiSyncSections();
                });
            });
            this.tcsiObserver.observe(root, {
                subtree: true, childList: true, attributes: true, attributeFilter: ["class"],
            });
        });
        onWillUnmount(() => {
            this.tcsiObserver?.disconnect();
            this.settingsRef.el?.removeEventListener("scroll", this.tcsiOnScroll);
            if (this.tcsiFrame) cancelAnimationFrame(this.tcsiFrame);
        });
    },
    tcsiSyncSections() {
        const root = this.settingsRef.el;
        if (!root) return;
        const sections = visibleSettingsSections(root, this.tcsiHeadingPrefix);
        this.tcsiTargets = new Map(sections.map(({ id, heading }) => [id, heading]));
        const items = sections.map(({ id, label }) => ({ id, label }));
        if (JSON.stringify(items) !== JSON.stringify(this.tcsiOutline.sections)) {
            this.tcsiOutline.sections = items;
        }
        this.tcsiSyncActiveSection();
    },
    tcsiSyncActiveSection() {
        const root = this.settingsRef.el;
        if (!root) return;
        const top = root.getBoundingClientRect().top + 40;
        let active = this.tcsiOutline.sections[0]?.id || "";
        for (const { id } of this.tcsiOutline.sections) {
            if (this.tcsiTargets.get(id)?.getBoundingClientRect().top <= top) active = id;
        }
        if (this.tcsiOutline.active !== active) this.tcsiOutline.active = active;
    },
    tcsiJumpToSection(id) {
        const root = this.settingsRef.el;
        const target = this.tcsiTargets.get(id);
        if (!root || !target) return;
        root.scrollTo({
            top: Math.max(0, target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop - 16),
            behavior: "auto",
        });
        this.tcsiOutline.active = id;
        target.focus({ preventScroll: true });
    },
});
