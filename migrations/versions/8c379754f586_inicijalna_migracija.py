"""inicijalna migracija

Revision ID: 8c379754f586
Revises: 
Create Date: 2025-02-16 09:09:26.630286

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c379754f586'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('partner',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=20), nullable=False),
    sa.Column('address', sa.String(length=200), nullable=True),
    sa.Column('city', sa.String(length=20), nullable=True),
    sa.Column('country', sa.String(length=20), nullable=True),
    sa.Column('pib', sa.String(length=20), nullable=True),
    sa.Column('mb', sa.String(length=20), nullable=True),
    sa.Column('phones', sa.String(length=20), nullable=True),
    sa.Column('fax', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=20), nullable=True),
    sa.Column('customer', sa.Boolean(), nullable=True),
    sa.Column('supplier', sa.Boolean(), nullable=True),
    sa.Column('other', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('project',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_name', sa.String(length=20), nullable=False),
    sa.Column('project_description', sa.String(length=200), nullable=True),
    sa.Column('project_value', sa.String(length=20), nullable=True),
    sa.Column('project_year', sa.String(length=4), nullable=True),
    sa.Column('archived', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('service',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service_name_rs', sa.String(length=20), nullable=False),
    sa.Column('service_name_en', sa.String(length=20), nullable=True),
    sa.Column('service_description', sa.String(length=200), nullable=True),
    sa.Column('service_value', sa.String(length=20), nullable=True),
    sa.Column('archived', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('archive', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('country', sa.String(length=20), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('archive', schema=None) as batch_op:
        batch_op.drop_column('country')
        batch_op.drop_column('city')

    op.drop_table('service')
    op.drop_table('project')
    op.drop_table('partner')
    # ### end Alembic commands ###
