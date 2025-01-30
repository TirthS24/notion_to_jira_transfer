# Zapier integration - add ability more fields than just system fields - different triggers than just 'added, etc

ID: 765
Type: User Story
Assignee: Meet Shah
Status: Backlog
Epic: Enhancement in StrAlign platform (../../../../../Epics%20e41f5e62b412478486ce2bf0ada44929/Enhancement%20in%20StrAlign%20platform%20eef7fb67fb5b4784aa4366cb162498ca.md)
Guild: Backend
Priority: P3-Normal
Short Description: Zapier integration - add ability more fields than just system fields - different triggers than just 'added, etc' (Meet has this detail)
Tags: Integration, New Development
Sum of child Story points: Spike task to check support for all stage fields in zapier,A new Zapier trigger to populate dropdown values of all available stage fields,Modify new item triggers,Modify updated item trigger,Modify Add item Action,Modify, update item actions to accept these stage field types from Zapier & Unit Testing,Modify Rankings trigger to send  all the stage fields data with current and previous rank to Zapier & Unit testing,List of Scenarios not supported in Zapier,Create a document on zaps creation flow
Total Duration: 0
Child Tasks: Spike task to check support for all stage fields in zapier (Spike%20task%20to%20check%20support%20for%20all%20stage%20fields%20i%206f4731d29a4d4cbda8e621b89483a2af.md), A new Zapier trigger to populate dropdown values of all available stage fields (A%20new%20Zapier%20trigger%20to%20populate%20dropdown%20values%20o%20fbfd066cbda54f73b0145390f14b8e30.md), Modify new item triggers (Modify%20new%20item%20triggers%209fbe6d8858f74f1a8db0de31cfdc1692.md), Modify updated item trigger (Modify%20updated%20item%20trigger%20cdd47e89da7146e0b0485a55fdd36fa0.md), Modify Add item Action (Modify%20Add%20item%20Action%204103ad610a8b4a17b2d0bcd0cb18eb7a.md), Modify, update item actions to accept these stage field types from Zapier & Unit Testing (Modify,%20update%20item%20actions%20to%20accept%20these%20stage%20%20fabdf8ddf5b14da0b572a7e47ec15557.md), Modify Rankings trigger to send  all the stage fields data with current and previous rank to Zapier & Unit testing (Modify%20Rankings%20trigger%20to%20send%20all%20the%20stage%20fiel%20f8e702bdc8754c719a78c6102869df25.md), List of Scenarios not supported in Zapier (List%20of%20Scenarios%20not%20supported%20in%20Zapier%20e454a6254c014a4c8157fbea74560bf3.md), Create a document on zaps creation flow (Create%20a%20document%20on%20zaps%20creation%20flow%2010d961f1e3ec8074862ccbd614761a10.md)

---

**Description:**
Zapier integration - add ability more fields than just system fields - different triggers than just 'added, etc' (Meet has this detail) - need to select one way or bi-directional. We’re increasing this existing functionality capability to support all the fields, not just system fields.

**Acceptance Criteria:**

- All the fields which are added on the platform should be show up on zapier.

Zapier integration - Ability to add additional fields.
Spike task to do POC for all stage field types - 1 Day

- A new trigger in Zapier to populate dropdown values of all available stage fields so that users can map those StrAlign fields against Smartsheet column names - 1.5 days
- Modify existing triggers and actions to use that trigger to show all available stage fields - 1 day
- Modify New item & Updated item trigger to send all the stage fields data (even the empty ones) to Zapier in the format required by Zapier (we will support all existing stage fields & Unit Testing - Dropdown, date, linked items, attachments, symbols, measurement fields) - 5 days
- Modify Add item, Update item actions to accept these same field types from Zapier & Unit Testing- 5 days
- Modify Rankings trigger to send all the stage fields data with current and previous rank to Zapier & Unit testing- 2 days

This doesn’t include sending Rankings data as Personalized/ Default view . (all the fields will be sent and users can choose on Zapier which ones they need)

**Flow Diagrams**

[https://www.notion.so](https://www.notion.so)