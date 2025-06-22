-- Enable the pgvector extension
create extension if not exists vector;

-- Drop tables if they exist (to allow rerunning the script)
drop table if exists crawled_pages;
drop table if exists code_examples;
drop table if exists sources;

-- Create the sources table
create table sources (
    source_id text primary key,
    summary text,
    total_word_count integer default 0,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create the documentation chunks table
create table crawled_pages (
    id bigserial primary key,
    url varchar not null,
    chunk_number integer not null,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    source_id text not null,
    embedding vector(1024),  -- OpenAI embeddings are 1024 dimensions
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(url, chunk_number),
    
    -- Add foreign key constraint to sources table
    foreign key (source_id) references sources(source_id)
);

-- Create an index for better vector similarity search performance
create index on crawled_pages using ivfflat (embedding vector_cosine_ops);

-- Create an index on metadata for faster filtering
create index idx_crawled_pages_metadata on crawled_pages using gin (metadata);

-- Create an index on source_id for faster filtering
CREATE INDEX idx_crawled_pages_source_id ON crawled_pages (source_id);

-- Create a function to search for documentation chunks
create or replace function match_crawled_pages (
  query_embedding vector(1024),
  match_count int default 10,
  filter jsonb DEFAULT '{}'::jsonb,
  source_filter text DEFAULT NULL
) returns table (
  id bigint,
  url varchar,
  chunk_number integer,
  content text,
  metadata jsonb,
  source_id text,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    url,
    chunk_number,
    content,
    metadata,
    source_id,
    1 - (crawled_pages.embedding <=> query_embedding) as similarity
  from crawled_pages
  where metadata @> filter
    AND (source_filter IS NULL OR source_id = source_filter)
  order by crawled_pages.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Enable RLS on the crawled_pages table
alter table crawled_pages enable row level security;

-- Create a policy that allows anyone to read crawled_pages
create policy "Allow public read access to crawled_pages"
  on crawled_pages
  for select
  to public
  using (true);

-- Enable RLS on the sources table
alter table sources enable row level security;

-- Create a policy that allows anyone to read sources
create policy "Allow public read access to sources"
  on sources
  for select
  to public
  using (true);

-- Create the code_examples table
create table code_examples (
    id bigserial primary key,
    url varchar not null,
    chunk_number integer not null,
    content text not null,  -- The code example content
    summary text not null,  -- Summary of the code example
    metadata jsonb not null default '{}'::jsonb,
    source_id text not null,
    embedding vector(1024),  -- OpenAI embeddings are 1024 dimensions
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    
    -- Add a unique constraint to prevent duplicate chunks for the same URL
    unique(url, chunk_number),
    
    -- Add foreign key constraint to sources table
    foreign key (source_id) references sources(source_id)
);

-- Create an index for better vector similarity search performance
create index on code_examples using ivfflat (embedding vector_cosine_ops);

-- Create an index on metadata for faster filtering
create index idx_code_examples_metadata on code_examples using gin (metadata);

-- Create an index on source_id for faster filtering
CREATE INDEX idx_code_examples_source_id ON code_examples (source_id);

-- Create a function to search for code examples
create or replace function match_code_examples (
  query_embedding vector(1024),
  match_count int default 10,
  filter jsonb DEFAULT '{}'::jsonb,
  source_filter text DEFAULT NULL
) returns table (
  id bigint,
  url varchar,
  chunk_number integer,
  content text,
  summary text,
  metadata jsonb,
  source_id text,
  similarity float
)
language plpgsql
as $$
#variable_conflict use_column
begin
  return query
  select
    id,
    url,
    chunk_number,
    content,
    summary,
    metadata,
    source_id,
    1 - (code_examples.embedding <=> query_embedding) as similarity
  from code_examples
  where metadata @> filter
    AND (source_filter IS NULL OR source_id = source_filter)
  order by code_examples.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- Enable RLS on the code_examples table
alter table code_examples enable row level security;

-- Create a policy that allows anyone to read code_examples
create policy "Allow public read access to code_examples"
  on code_examples
  for select
  to public
  using (true);