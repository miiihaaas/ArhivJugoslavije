"""dodata kolona account_type u BankAccount

Revision ID: 7462a2a52443
Revises: 0e48a68791fe
Create Date: 2025-05-04 19:34:57.859728

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7462a2a52443'
down_revision = '0e48a68791fe'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('bank_account', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_type', sa.String(length=50), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('bank_account', schema=None) as batch_op:
        batch_op.drop_column('account_type')

    # ### end Alembic commands ###
