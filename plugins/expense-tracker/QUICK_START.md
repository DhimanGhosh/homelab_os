# Expense Tracker Quick Start

## Start

Run the plugin through your Homelab OS plugin flow, or start the Docker service from `homelab_os/plugins/expense-tracker/docker`.

The app listens on internal port `8161` and public port `8461`.

## First Steps

1. Open the Dashboard.
2. Set Current Bank Balance.
3. Add expenses from Quick Add or Transactions.
4. Add credits from Transactions with type `Income / Credit`.
5. Create monthly or yearly items in Recurring Expenses.
6. Review Dashboard and Analytics for charts, smart notes, and investment ideas.

## Smart Categorization

Type a description such as `Blinkit groceries` or `Netflix subscription`. The app predicts a category locally:

- ML is used after enough local transaction history exists.
- Keyword rules are used as fallback.
- You can type a new category directly; it will appear in category suggestions after saving.

## Bank Balance

The balance is a single global current bank balance.

- Expenses are stored as negative values and reduce the balance.
- Credits are stored as positive values and increase the balance.
- Editing a transaction applies only the delta.
- Deleting a transaction reverses its effect.

## Recurring Expenses

Recurring templates are projected into Dashboard, Budget, and Analytics totals even before the scheduler creates the real expense row. If an auto-generated row already exists, the projection avoids double counting it.

## Version

This quick start applies to Expense Tracker `1.1.0`.
