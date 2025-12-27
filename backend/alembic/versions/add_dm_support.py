"""Add DM support - conversations and messages tables

Revision ID: add_dm_support
Revises: add_video_urls
Create Date: 2024-12-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_dm_support'
down_revision = 'add_video_urls'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add DM settings to personas table
    op.add_column('personas', sa.Column('dm_prompt_template', sa.Text(), nullable=True))
    op.add_column('personas', sa.Column('dm_auto_respond', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('personas', sa.Column('dm_response_delay_min', sa.Integer(), nullable=True, server_default='30'))
    op.add_column('personas', sa.Column('dm_response_delay_max', sa.Integer(), nullable=True, server_default='300'))
    op.add_column('personas', sa.Column('dm_max_responses_per_day', sa.Integer(), nullable=True, server_default='50'))
    op.add_column('personas', sa.Column('dm_responses_today', sa.Integer(), nullable=True, server_default='0'))
    
    # Create enums only if they don't exist
    connection = op.get_bind()
    
    # Check and create conversation status enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'conversationstatus'"))
    if not result.fetchone():
        conversation_status = postgresql.ENUM('active', 'paused', 'closed', 'blocked', name='conversationstatus')
        conversation_status.create(connection)
    
    # Check and create message direction enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'messagedirection'"))
    if not result.fetchone():
        message_direction = postgresql.ENUM('inbound', 'outbound', name='messagedirection')
        message_direction.create(connection)
    
    # Check and create message status enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'messagestatus'"))
    if not result.fetchone():
        message_status = postgresql.ENUM('received', 'pending_response', 'responded', 'failed', 'ignored', name='messagestatus')
        message_status.create(connection)
    
    # Get enum types (already created above)
    conversation_status_enum = postgresql.ENUM('active', 'paused', 'closed', 'blocked', name='conversationstatus', create_type=False)
    message_direction_enum = postgresql.ENUM('inbound', 'outbound', name='messagedirection', create_type=False)
    message_status_enum = postgresql.ENUM('received', 'pending_response', 'responded', 'failed', 'ignored', name='messagestatus', create_type=False)
    
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('persona_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('personas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),
        sa.Column('platform_conversation_id', sa.String(100), nullable=True),
        sa.Column('participant_id', sa.String(100), nullable=False),
        sa.Column('participant_username', sa.String(100), nullable=True),
        sa.Column('participant_name', sa.String(200), nullable=True),
        sa.Column('participant_profile_url', sa.String(500), nullable=True),
        sa.Column('status', conversation_status_enum, server_default='active'),
        sa.Column('message_count', sa.Integer(), server_default='0'),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_response_at', sa.DateTime(), nullable=True),
        sa.Column('context_summary', sa.Text(), nullable=True),
        sa.Column('is_follower', sa.Boolean(), server_default='false'),
        sa.Column('is_verified', sa.Boolean(), server_default='false'),
        sa.Column('requires_human_review', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    
    # Create direct_messages table
    op.create_table(
        'direct_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('platform_message_id', sa.String(100), nullable=True),
        sa.Column('direction', message_direction_enum, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('media_urls', sa.Text(), nullable=True),
        sa.Column('status', message_status_enum, server_default='received'),
        sa.Column('ai_generated', sa.Boolean(), server_default='false'),
        sa.Column('generation_prompt', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('read_at', sa.DateTime(), nullable=True),
    )
    
    # Create indexes for faster queries
    op.create_index('ix_conversations_persona_id', 'conversations', ['persona_id'])
    op.create_index('ix_conversations_platform', 'conversations', ['platform'])
    op.create_index('ix_conversations_participant_id', 'conversations', ['participant_id'])
    op.create_index('ix_direct_messages_conversation_id', 'direct_messages', ['conversation_id'])
    op.create_index('ix_direct_messages_status', 'direct_messages', ['status'])


def downgrade() -> None:
    op.drop_index('ix_direct_messages_status')
    op.drop_index('ix_direct_messages_conversation_id')
    op.drop_index('ix_conversations_participant_id')
    op.drop_index('ix_conversations_platform')
    op.drop_index('ix_conversations_persona_id')
    
    op.drop_table('direct_messages')
    op.drop_table('conversations')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS messagestatus')
    op.execute('DROP TYPE IF EXISTS messagedirection')
    op.execute('DROP TYPE IF EXISTS conversationstatus')
    
    # Remove persona columns
    op.drop_column('personas', 'dm_responses_today')
    op.drop_column('personas', 'dm_max_responses_per_day')
    op.drop_column('personas', 'dm_response_delay_max')
    op.drop_column('personas', 'dm_response_delay_min')
    op.drop_column('personas', 'dm_auto_respond')
    op.drop_column('personas', 'dm_prompt_template')

