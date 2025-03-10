"""dodate kolone u Partner

Revision ID: 3ed293c64d2e
Revises: 8c379754f586
Create Date: 2025-02-16 10:35:11.319967

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ed293c64d2e'
down_revision = '8c379754f586'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('partner', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_number', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('international', sa.Boolean(), nullable=True))
        batch_op.drop_column('other')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('partner', schema=None) as batch_op:
        batch_op.add_column(sa.Column('other', sa.BOOLEAN(), nullable=True))
        batch_op.drop_column('international')
        batch_op.drop_column('account_number')

    # ### end Alembic commands ###
