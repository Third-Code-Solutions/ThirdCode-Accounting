# Company Discuss isolation

Objective: customer General, Discuss channels, direct chats, messages, membership and realtime delivery must stay within their organization. Platform owner uses a separate internal support/moderation workspace.

Observed cause: native General subscribes base.group_user globally. Existing contact filtering redacts identities but deliberately retained shared channel message bodies. This is insufficient for chat confidentiality.

Acceptance: enforce server-side company scope, including owner exclusion from customer chats; prevent cross-company membership and forged channel targets; deny foreign history/search/export/attachments/realtime; provision company General and platform staff channels; retain ambiguous mixed legacy history without exposing or copying it to customers. Verify positive same-company communication and provisioning plus negative tenant/owner boundaries in native CI, then verify deployed discovery/history using existing accounts without sending production messages.

Checkpoint: implementation in progress. Existing native channel, membership, mail-message and public invitation controller paths inspected. Upgrade will retain all message rows and restrict mixed channels instead of guessing message ownership.
