# HW5 — AI Prompts Log

This is a log of the prompts typed to the AI coding assistant (Claude Code) while completing Homework 5.
Prompts are copied word for word and grouped by problem, in the order they were typed. When a follow-up prompt was needed, one sentence explains what the first prompt was missing.

---

## Setup

**Prompt 1 (assignment overview, shared with a screenshot of the assignment intro):**
> We are going to do homework 5 of AI. A little bit of context, it comes from th same idea of homework 4. Campus Customs Multi agent operations is the agentic team that runs the shop. see the screenshot, but dont do anything at all, just read

**Prompt 2 (database and shop rules):**
> I already clear that folder and put the files we will need for AI. There is the file data/campus_customs.db. That file is the original shop database. Tables include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments and invoices. Our tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db and point your MCP server and backend at that working copy. Keep campus_customs.db untouched so we can reset when we want to restart resoliving the tickets. There are some rule of the shop to take into account. The field desk.date_today is today for the shop, use this date to determine what is overdue. Vendor lead times come from the vendors table. A vendor will no ship new product while the still have an open unpaid invoice. Human approval is required for any payments. Points will be deducted if this not done. If payment is made, make sure to update the relevant table. If there is not enough cash, the pay tool must refuse, there for there shouldnt be negative balances. Cash only goes out in this homwork, they didnt model revenue, so no mones comes in. Before a full run to resolve the tickets, make sure to rest the databse to the original values. DO not email customers or call real vendors, drafts stay on the board. Dont do nothing yet, this is all context

---

## Problem 1 — Vibe Coder Prompts

**Prompt 1:**
> So, now we are in problem 1: vibe coder prompts. Create AI_prompts.md at the start of the assignment and keep it updated as you work. This file is the log of what I'll type you from now on. Put one section for each problem. Each section must include: the problem number and title, at least one prompt you typed in your own words as much as possible, one follow-up prompt if you needed it (and one sentence on what was lacking after the first)

---

## Problem 2 — Study the Campus Customs Database

**Prompt 1:**
> Now problem 2: study th campus customs database. Open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db, and late problems update that working copy. Please study the three open tickets so you see how they link to other tables. Start output/harness.md. For each table, list the fields and one short line on why that table matters for the agents. You will keep growing this harness fil in later problems

---

## Problem 3 — Build the MCP Server

**Prompt 1:**
> Now problem 3: build the MCP server. Write and MCP server in mcp_sever/ using FastMCP. It will talk to data/campus_customs_new.db. You dont need to connect or run it in this problem. Every agent in this homework uses the tools in this MCP server. You will add more tools to it later: for now, write three tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database. In output/harness.md, list each of your three MCP tools. For every tool include: which tabl it reads, which ticket it helps unlock (101, 102 or 103) and one sentence on why that toool is the right one for that ticket. Vague lines like reads inventory score low, so please create good lines and tie the tool to the ticket. Also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses and the three tools it has

---

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

**Prompt 1:**
> Now problem 4, Add the MCP server to vibe coder and test each tool. So please add my MCP server to this project si that you can call the tools. Save the connection JSON text in .mcp.json at the project root or however you save local MCP sever lists. When you are connected, test each of our three MCP tools. Save the evidence in output/mcp_smoke.json. FOr every tool include: the prompt you asked the vibe coder, the tool name and the tool output (must match values in data/campus_customs_new.db)

**Prompt 2 (tool test):**
> Use check_stock to see if we can fill ticket 101

**Prompt 3 (tool test):**
> Use get_vendor_status to see why we can't restock the tee

**Prompt 4 (tool test):**
> Use get_rent_status to check if ticket 102 rent is overdue

---

## Problem 5 — Build the Agent Team and Grow the MCP Tools

**Prompt 1:**
> Perfect. Lets go to problem 5: Build the agent team and grow the MCP tools. In this problem build the agentic team for Campus Customs using Pydantic AI: Boss, Inventory, Accounting, Facilities and Customer Service. Include prompts, models and agent loops so they can delegate work to each other with full connectivity. Put the agent prompts in backend/prompts/, making one file per agent. Put data types in backend/models.py and the agent files under backend/. Your layout can vary as long as the five roles are clear. For this use our PORTKEY_API_KEY and only gpt-6-luna for every agent. Write each prompt as if I was writing it with the shop rules that agent needs. More detailed prompts that cover all aspects of an agents work and scope score higher than a short generic prompt. Add any tools the agents need to your MCP server so they can work on the open tickets. Shop facts come from the MCP sever over data/campus_customs_new.db do not invent a second shop-tools layer that bypasses MCP. Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file, do not wipe it each run. In output/harness.md list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. Also add a short safety section: the guardrails a real business world would want when agent have real customers data, information and money. Plus limits that keep token use in check. Update mcp_server/README.md so the tool list matches what I have now

---

## Problem 6 — Plan the Three Tickets

**Prompt 1:**
> Keep the discount policy, lets go to problem 6. Its title is plan the three tickets. The idea in this problem is that before we wire the backend, we have to write down what we expect the team to do on each open tickts. So, build output/desk_tickets.html, that should be a page where we can double-click with one tab per ticket (101, 102 and 103). Also add empty cash and reflection tabs for later problems, leaving them blank or with a short coming later note for now. On each ticket tab, fill an expected section only, leaving room for an actual section we will fill after we run the agents. For each tickets expect section, write in my own words: who the boss should call first and why, All the agent delegation that we expect, there shouldnt be Boss calls everyone, and which MCP tools you expect that run to use. Take into consideration that plans that send every specialist on every ticket score low. We will compare this plan to what actually happens when our agents resolve the three tickets

---

## Problem 7 — Backend Routes

**Prompt 1:**
> Lets go to problem 7. Called Backend routes. The frontend dashboard that we are going to make in the next problem, needs a backend it can call. In backend/main.py use FastAPI and add routes that do: 1. Return the three tickets and whether each is open or resolved 2. Take a ticket id and run yout agent team on that ticket 3.  Return recent agent events, what each agent said and which toold they used, making possible that the board can refresh. 4. Also, approve a payment or purchase after a human clicks approve (agents only prepare the pay, this route is what actually changes cash).  5. It is key to return the current checking balance from cash_accounts. 6. Rest the database to the original values when you want to try a fresh run. Please alfo from the backend/ folder start the server with: uvicorn main:app --reload --port 8000. This turns our backend a http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line (what URL/what it does)

---

---

## Problem 8 — Agent Dashboard

**Prompt 1:**
> Let go to problem 8, the title is Agent dashboard. Here please build the dashboard in frontend/ with React+Vite+TypeScript. The page should call the routes you built in the backend during problem 7. At minimum the board should: 1. List all three tickets, 2. Le you pick one ticket and start the agent team on it 3. show each agent and what they are saying and doing while the ticket runs. 4. mark a ticket resolved when the run finishes. 5. Show a short summary of what each agent did on that tickt 6. Let a human approve a pay or purchas when asked 7. show th checking balance (it should drop after an apporved pay). Include something creative and functional that comes to your mind. The idea is that the dashboards looks good, but without falling in your usual template, so please bbe creative with the layout and feel, having into account this is a real desk people would people want to sit at, so take some time thinking in the experience and how it looks. It is key the the front end talks to the backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call thos routes. Start th board with: npm run dev. In theory, this opens the react desk in the browser for me to pick tickets and watch agents. Write output/design.md with what we chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why, including creative choices that make it feel special and something humans would actually enjoy using

**Prompt 2 (follow-up):**
> i dont like that much the circle in the background. Can you do something nicer?

*What was lacking after the first prompt:* the round wooden table in the middle of the desk looked generic and cartoonish, so it was replaced with a green leather desk blotter that fits the back-office feel.

**Prompt 3 (follow-up):**
> No i still dont like it. leave it without figure in the background. Im trying to sign but Im not able, why?

*What was lacking after the previous prompt:* the leather blotter still distracted from the agents, so the background shape was removed. The only place to sign was a small "Signing as" field, and the Sign & pay button stayed disabled with no explanation. Now you sign directly on the check's signature line, and a note says what's missing.

**Prompt 4 (follow-up):**
> still something feels off, i think yes we need a figure in the background but still i havent like anything you hav sent for it

*What was lacking after the previous prompt:* the desk felt empty without a background, but none of the earlier shapes fit. Four different concepts were sketched to choose from: shop floor plan, corkboard with red string, cutting mat, and crest watermark.

**Prompt 5 (choice):**
> Use option B: the corkboard with red string hand-offs

---

## Problem 9 — Resolve the Tickets

**Prompt 1:**
> lets go to problem 9. The title is Resolve the tickets. Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so we can start clean. Note the starting checking balance. Then run all three tickets on the board (101,102,103) until each is resolved. Open output/desk_tickets.html from problem 6. On  each tickt tab, fill the actual section from this rum: which agents worked, what they delegated, and which tools they used. Keep your expected section so you can compare the two. On the cash tab of the same output/desk_tickets.html itemize the money: starting checking balance (after the reset), for each tickt show cash changed when that ticket resolved and why, including which pay/purchase and the dollar amount. Ending checking balance, being aware that it must match cash_accounts in the working databse. Wrong cash math loses points even if th board shows every ticket resolved. ALso save: output/resolved_tickets.json, for each ticket include: id, final status, short outcome, what each agent contributes, and any human approvals. output/resolved_board.hrml, a page where I can double click with a screenshot of your react board for each resolved ticket (101, 102 and 103) Append real runs to output/audit_trail.son. Finish output/harnss.md so it covers tables, MCP tools the five agents, API routes, the dashboard and safety rules

**Prompt 2 (human approval decision):**
> Approve as Juan Pablo *(answer to the question of how to approve the two pending checks: #1 for $840 and #2 for $2,400)*


---

## Problem 10 — Reflection

**Prompt 1:**
> we are now in problem 10, with the title of refelction. help me opening the desk_tickets.html for me to check the ticket tab and cash tab

**Prompt 2:**
> perfect, so in this problem help me opening output/desk_tickets.hrml and fill the reflection tab. I prepare the following paragaphs, and attach the screenshots (these paragraphs' grammar and syntaxis were checked by Claude): *(followed by my three reflection paragraphs, now on the Reflection tab of output/desk_tickets.html, and screenshots of the Ticket and Cash tabs I reviewed)*

**Prompt 3 (follow-up):**
> just leave them as evidence in the prompt or maybe in the reflection tab, put an appendix section with those screenshots

*What was lacking after the previous prompt:* the screenshots I attached weren't saved anywhere. They are now in `output/screenshots/reflection/` and shown as an appendix (A1–A8) at the end of the Reflection tab.

---

## Problem 11 — Submit to GitHub

**Prompt 1:**
> Now lets go with the last question! its problem 11: Submit to Github. So push the code to a public Git Hub repository so graders can clone it. I'll need a URL and an output/github_url.txt file. Please do not push the real .env to the GitHub repo, and do include both database files under data/ (the orginal and our working copy) co graders can run the app easily. See the attached screnshot for the expected file layout. README should explain, copy original D to the working copy when you need a clean run, start MCP srver, start FastAPI backend, start the React board, reset the DB before a full three-ticket run
