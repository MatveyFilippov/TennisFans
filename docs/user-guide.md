# Player, organizer, and administrator guide

Use the language selector for English or Russian and the theme selector for light, dark, or device appearance. You can browse the leaderboard, profiles, comparisons, matches, and tournaments without signing in. After installation as a progressive web app, previously loaded public views can be read offline. Submit results, applications, and photos while connected.

## Player

1. Select **Create account**, choose a unique username, and use a password with 12–128 characters. Username matching is case-insensitive.
2. In **Account**, change your display name, set a profile photo, or rotate your password using the current password. Recent dispute decisions appear in **Notifications**.
3. Select **Record a friendly match**, choose singles or doubles, select the other registered players, choose scoring rules, and enter the actual playing date, winner and set scores. Your side always includes you.
4. For a tournament, select **Apply** when applications are open. A pending application can be withdrawn before startup. An accepted player is listed in the roster.
5. Open your fixture from the tournament schedule and choose **Submit result**. Competitive results affect the global rating immediately. Use the actual technical outcome if a fixture ends by walkover, forfeit, or retirement. An administrator can enter a technical outcome if neither side can submit it.
6. If an opposing participant entered an incorrect result, open the match and choose **Dispute result**. Write a reason suitable for public display. The result remains visible and stops contributing to ratings or progression while under review.
7. Match participants can upload JPEG, PNG or WebP photos in one or several batches.

## Assigned organizer

Open your assigned tournament. Review applications, accept within capacity, reject, add registered players directly, or remove a roster member before startup. For fixed doubles, pair accepted players in disjoint teams and save. Upload photos from a tournament or match page.

You can arbitrate a dispute in an assigned tournament if you did not play the match. Record the reason and choose **Uphold result** or **Replace score**. Ask an administrator to handle a replacement that would invalidate recorded downstream results.

## Administrator

Add an administrator first with the [bootstrap command](deployment-ubuntu.md). In the tournament list, select **Create tournament**. Set player slots, format, scoring, date and time zone, and optionally include players and organizers. Assign and revoke organizers from the tournament page. If automatic startup finds an incomplete roster, set a new start time after the roster is ready, or delete the tournament.

Use a match page to correct a result, arbitrate, annul, or permanently delete it. When the change affects dependent fixtures, the application lists them for review and requests confirmation. An annulment informs all participants. Manage users and read the audit trail in **Administration**. A password reset ends existing sessions. Give the short-lived, single-use password to the user through a private channel. The user sets a new password before continuing.
