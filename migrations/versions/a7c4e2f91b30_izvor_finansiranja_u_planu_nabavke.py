"""izvor finansiranja u planu nabavke

Revision ID: a7c4e2f91b30
Revises: d11cef134645
Create Date: 2026-11-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c4e2f91b30'
down_revision = 'd11cef134645'
branch_labels = None
depends_on = None


def upgrade():
    # Postojeće stavke plana su unete za izvor 01 (budžet) - server_default ih tako i popunjava
    with op.batch_alter_table('purchase_plan_account', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=2), nullable=False, server_default='01'))


def downgrade():
    with op.batch_alter_table('purchase_plan_account', schema=None) as batch_op:
        batch_op.drop_column('source')
