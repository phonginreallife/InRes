# Access Control Guide

## How Permissions Work in InRes

This guide explains who can see what in InRes. Think of it like a building with different rooms - some people have keys to certain rooms, others don't.

---

## Quick Summary

| Term | What It Means |
|------|---------------|
| **Organization** | Your company or team workspace (like "Acme Corp") |
| **Project** | A folder within your organization (like "Platform", "Security") |
| **Open Project** | Everyone in the org can see it |
| **Closed Project** | Only specific people can see it |

---

## The Building Analogy 🏢

Think of inres like an office building:

```
🏢 ACME CORP (Organization)
│
├── 🚪 Reception (Open to all employees)
│   └── Anyone with an employee badge can enter
│
├── 🔒 Server Room (Closed - Security Team only)
│   └── Only people with server room keys can enter
│
├── 🔒 Executive Suite (Closed - Leadership only)
│   └── Only executives have access
│
└── 🚪 Cafeteria (Open to all employees)
    └── Anyone with an employee badge can enter
```

In InRes:
- **Organization** = The building (Acme Corp)
- **Projects** = Different rooms in the building
- **Open Project** = Unlocked room (all employees can enter)
- **Closed Project** = Locked room (only people with keys can enter)

---

## User Roles Explained

### Organization Roles

| Role | Who They Are | What They Can Do |
|------|--------------|------------------|
| 🔑 **Owner** | The founder/CEO | Everything - including deleting the organization |
| 👔 **Admin** | Managers | Add/remove people, change settings, manage projects |
| 👤 **Member** | Regular employees | Create incidents, view data, work on projects |
| 👁️ **Viewer** | Observers | Can only look, cannot change anything |

### Project Roles

| Role | What They Can Do |
|------|------------------|
| 👔 **Admin** | Full control over the project |
| 👤 **Member** | Create and update resources |
| 👁️ **Viewer** | Read-only access |

---

## Open vs Closed Projects

This is the most important concept!

### Open Project 🚪
- **No specific people assigned** to the project
- **Everyone** in the organization can see it
- Good for: Shared projects, company-wide initiatives

### Closed Project 🔒
- **Has specific people assigned** to it
- **Only those people** can see it
- Other org members (even admins!) cannot see it
- Good for: Sensitive projects, team-specific work

### How Projects Become Closed

When you **create a new project**, you automatically become its owner. This makes the project **closed** immediately.

```
You create "Secret Project" 
    ↓
You're added as the owner
    ↓
Project is now CLOSED
    ↓
Only you can see it!
```

**To let others see it**, you must either:
1. Add them as project members, OR
2. Remove yourself (makes project "open" - but you lose access too!)

---

## Real-World Examples

### Example 1: New Employee Joins

**Situation**: Sarah joins Acme Corp as a Member

**What Sarah can see:**
-   All **Open** projects
-   Incidents not linked to any project
-   Any incident assigned directly to her
- ❌ **Closed** projects (unless someone adds her)

### Example 2: Admin Can't See a Project

**Situation**: Bob is an Org Admin, but can't see the "Platform" project

**Why?**: The Platform project has specific members (it's **Closed**)

**Solution**: Someone with Platform project access must add Bob as a member

### Example 3: Creating a Team Project

**Situation**: You want to create a project for your team of 5 people

**Steps**:
1. Create the project (you become owner - project is now **Closed**)
2. Go to Project Settings → Members
3. Add your 4 teammates
4. Now all 5 of you can see the project

### Example 4: Creating a Company-Wide Project

**Situation**: You want everyone to see a project

**Option A** - Add everyone as members (tedious)

**Option B** - Make it **Open**:
1. Create the project
2. Remove yourself as a member
3. Now it's **Open** - everyone can see it
4. ⚠️ Note: You can still see it because you're in the org

---

## Who Can See What?

### Incidents

| Incident Location | Who Can See It |
|-------------------|----------------|
| No project (org-level) | All org members |
| Open project | All org members |
| Closed project | Only project members |
| Assigned to you | You (even if you can't see the project) |

### Groups (On-Call Teams)

| Group Visibility | Who Can See It |
|------------------|----------------|
| Public/Organization | All org members |
| Private | Only group members |

---

## Common Questions

### "Why can't I see any incidents?"

**Check these things:**
1. Are you looking at the right organization?
2. Is there a project filter selected? Try "All Projects"
3. Are the incidents in a **Closed** project you don't have access to?

### "I'm an Admin - why can't I see this project?"

Being an **Org Admin** doesn't automatically give you access to **Closed Projects**. Someone needs to add you as a project member.

Think of it like this: The building manager (Admin) doesn't automatically have keys to the CEO's private office (Closed Project).

### "How do I give my whole team access to a project?"

1. Go to the project
2. Click "Members" or "Settings"
3. Add each team member one by one
4. Choose their role (Admin, Member, or Viewer)

### "How do I make a project visible to everyone?"

You have two options:

**Option 1**: Add everyone as members (good for tracking who has access)

**Option 2**: Make it an **Open** project by removing all specific members

---

## Permission Summary Chart

```
                        Can See Open    Can See Closed    Can Manage
Role                    Projects?       Projects?         Members?
─────────────────────────────────────────────────────────────────────
Org Owner                 Yes          ❌ No*              Yes
Org Admin                 Yes          ❌ No*              Yes  
Org Member                Yes          ❌ No*            ❌ No
Org Viewer                Yes          ❌ No*            ❌ No

Project Admin           N/A               Yes              Yes
Project Member          N/A               Yes            ❌ No
Project Viewer          N/A               Yes            ❌ No

* Unless explicitly added as a project member
```

---

## Tips for Administrators

### Setting Up a New Team Member

1. **Add them to the Organization** with appropriate role
2. **Add them to relevant Projects** they need to work on
3. **Add them to On-Call Groups** if they'll be on rotation

### Managing Project Access

- Use **Open projects** for company-wide visibility
- Use **Closed projects** for sensitive or team-specific work
- Regularly audit project members to ensure correct access

### Best Practices

1. **Start Closed, Open Later**: It's easier to grant access than to revoke it
2. **Use Descriptive Project Names**: Makes it clear what each project is for
3. **Document Access Requirements**: Keep a record of who needs access to what
4. **Regular Access Reviews**: Quarterly check that the right people have access

---

## Need Help?

If you're having access issues:

1. **Check your organization** - Are you in the right one?
2. **Check project membership** - Ask an admin to verify your access
3. **Contact your admin** - They can add you to projects you need

---

*This guide covers the basics of access control in InRes. For technical implementation details, see the [Technical ReBAC Documentation](./rebac-technical.md).*
