"""dodata kolona note u StatementItem

Revision ID: 4cc06ff15fc0
Revises: e406bea110f1
Create Date: 2025-05-04 14:21:50.191339

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4cc06ff15fc0'
down_revision = 'e406bea110f1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('statement_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('note', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('statement_item', schema=None) as batch_op:
        batch_op.drop_column('note')

    # ### end Alembic commands ###
