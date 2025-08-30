-- vim: set sw=2 et:
-- Based on: https://bennett.dev/auto-link-pipewire-ports-wireplumber/
--
-- This script ensures that ONLY the default source/sink are connected to REAPER,
-- and not ALL available sources/sinks.
-- It is an attempt to fix stuttering e.g. https://gitlab.freedesktop.org/pipewire/pipewire/-/issues/2314
--
-- To install:
-- mkdir ~/.config/wireplumber/wireplumber.conf.d
-- Create ~/.config/wireplumber/wireplumber.conf.d/99-auto-connect-ports.conf containing:
-- wireplumber.components = [
--   {
--     name = /path/to/REAPER-plugins/auto-connect-ports.lua, type = script/lua
--     provides = custom.auto-connect-ports
--   }
-- ]
-- wireplumber.profiles = {
--   main = {
--     custom.auto-connect-ports = required
--   }
-- }
--
-- Or, if you want to run the plugin on the command line (for debugging),
-- replace the "wireplumber.profiles" section with:
-- wireplumber.profiles = {
--   auto-connect-ports = {
--     inherits = [ base ]
--     support.standard-event-source = required
--     custom.auto-connect-ports = required
--   }
-- }
-- and run: wireplumber -p auto-connect-ports

cutils = require ("common-utils")

-- Goal: REAPER's first input/output ports
-- should be linked to the default source/sink ports.
-- The default sink monitor L/R should be linked to the REAPER's input 19-20.
-- The Blue Yeti microphone input should be linked to REAPER's input 11-12.

local all_nodes = ObjectManager {
  Interest {
    type = "node",
  }
}

local output_om = ObjectManager {
  Interest {
    type = "port",
    Constraint { "port.direction", "equals", "out" }
  }
}

local input_om = ObjectManager {
  Interest {
    type = "port",
    Constraint { "port.direction", "equals", "in" }
  }
}

-- Link two ports together
function link_port(output_port, input_port)
  if not input_port or not output_port then
    return nil
  end

  local link_args = {
    ["link.input.node"] = input_port.properties["node.id"],
    ["link.input.port"] = input_port.properties["object.id"],

    ["link.output.node"] = output_port.properties["node.id"],
    ["link.output.port"] = output_port.properties["object.id"],
    
    -- The node never got created if it didn't have this field set to something
    ["object.id"] = nil,

    -- I was running into issues when I didn't have this set
    ["object.linger"] = true,

    ["node.description"] = "Link created by auto_connect_ports"
  }

  local link = Link("link-factory", link_args)
  link:activate(1)

  return link
end

local auto_connect = {
  {
    input = { portfmt = "REAPER:in%d", from = 1 },
    output = {
      { portfmt = "Scarlett 4i4 USB:capture_AUX%d", from = 0 },
      { default_source = true },
    },
  },
  {
    output = { portfmt = "REAPER:out%d", from = 1 },
    input = {
      { portfmt = "Scarlett 4i4 USB:playback_AUX%d", from = 0 },
      { default_sink = true, min_count = 4 },
    },
  },
  {
    output = { portfmt = "REAPER:out%d", from = 7 },
    input = { default_sink = true, min_count = 2 },
  },
  {
    output = { portfmt = "REAPER:out%d", from = 11 },
    input = {
      { portfmt = "Blue Microphones:playback_%s", ports = { "FL", "FR" } },
      { portfmt = "Blue Microphones:playback_%s", ports = { "AUX0", "AUX1" } },
    }
  },
  {
    input = { portfmt = "REAPER:in%d", from = 11 },
    output = {
      { portfmt = "Blue Microphones:capture_%s", ports = { "FL", "FR" } },
      { portfmt = "Blue Microphones:capture_%s", ports = { "AUX0", "AUX1" } },
    }
  },
  {
    output = { portfmt = "REAPER:out%d", from = 13 },
    input = {
      -- Note, for Yeti Nano, be sure to select "Analog Stereo Duplex" as the profile,
      -- so that the pipewire volume knob controls the hardware's gain.
      -- If "Pro Audio" is selected, the pipewire volume knob is a simple
      -- filter on the microphone signal, which will be highly susceptible to clipping.
      -- Ref: https://bbs.archlinux.org/viewtopic.php?pid=2095461#p2095461
      { portfmt = "Yeti Nano:playback_%s", ports = { "FL", "FR" } },
      { portfmt = "Yeti Nano:playback_%s", ports = { "AUX0", "AUX1" } },
    }
  },
  {
    input = { portfmt = "REAPER:in%d", from = 13 },
    output = {
      { portfmt = "Yeti Nano:capture_%s", ports = { "FL", "FR" } },
      { portfmt = "Yeti Nano:capture_%s", ports = { "AUX0", "AUX1" } },
    }
  },
  {
    input = { portfmt = "REAPER:in%d", from = 19 },
    output = { default_sink_monitor = true },
  },
  {
    output = { portfmt = "REAPER:out%d", from = 7 },
    input = { portfmt = "Headphones:playback_%s", ports = { "FL", "FR" } },
  },
}

local input_checks = nil
local output_checks = nil

function get_auto_connect_links()
  local metadata = cutils.get_default_metadata_object()
  if not metadata then
    print("No metadata")
    return {}
  end

  function get_default_node_id(d)
    -- d should be "default.audio.source" or "default.audio.sink"
    local default_json = metadata:find (0, d)
    if not default_json then
      -- No default - probably the system is still initializing
      return nil
    end
    local default_name = Json.Raw (default_json):parse ().name
    if not default_name then
      print(string.format("No default name for %s", d))
      return nil
    end
    local default_node = all_nodes:lookup { Constraint { "node.name", "equals", default_name } }
    if not default_node then
      -- No default - probably the system is still initializing
      return nil
    end
    return default_node.properties["object.id"]
  end

  input_checks = {}
  output_checks = {}

  function find_port(cache, om, i)
    local port = om:lookup { Constraint { "port.alias", "equals", i } }
    if port then
      cache[i] = 222
    else
      cache[i] = 111
    end
    return port
  end

  function get_default_ports(d, om, min_count)
    -- d should be "default.audio.source" or "default.audio.sink"
    local node_id = get_default_node_id(d)
    local found = {}
    if node_id then
      local by_port_id = {}
      for port in om:iterate { Constraint { "node.id", "equals", tostring(node_id) } } do
        -- ipairs() doesn't seem to want to return index 0,
        -- so ensure that by_port_id indexes start from 1.
        by_port_id[1 + tonumber(port.properties["port.id"])] = port
      end
      for _id, port in ipairs(by_port_id) do
        table.insert(found, port)
      end
      if #found > 0 and min_count then
        while #found < min_count do
          for _id, port in ipairs(by_port_id) do
            table.insert(found, port)
          end
        end
      end
      --if #found == 0 then
      --  print(string.format("Did not find any ports on %s with id %d", d, node_id))
      --end
    end
    return function (i) return found[i] end
  end

  function resolve_ports(cache, om, specs)
    local specs = specs[1] == nil and { specs } or specs
    for _i, spec in ipairs(specs) do
      local found = nil
      if spec.default_sink then
        return get_default_ports("default.audio.sink", input_om, spec.min_count)
      elseif spec.default_source then
        return get_default_ports("default.audio.source", output_om, spec.min_count)
      elseif spec.default_sink_monitor then
        return get_default_ports("default.audio.sink", output_om, spec.min_count)
      elseif spec.ports then
        local portname = string.format(spec.portfmt, spec.ports[1])
        local port = find_port(cache, om, portname)
        if port then
          return function (i)
            return spec.ports[i] and find_port(cache, om, string.format(spec.portfmt, spec.ports[i]))
          end
        end
      else
        local portname = string.format(spec.portfmt, spec.from)
        local port = find_port(cache, om, portname)
        if port then
          return function (i)
            local portname = string.format(spec.portfmt, spec.from + i - 1)
            return find_port(cache, om, portname)
          end
        end
      end
    end
  end

  local links = {}
  for j, link in pairs(auto_connect) do
    local input = resolve_ports(input_checks, input_om, link.input)
    local output = resolve_ports(output_checks, output_om, link.output)
    --if not input then
    --  print(string.format("auto_connect[%d]: no input", j))
    --end
    --if not output then
    --  print(string.format("auto_connect[%d]: no output", j))
    --end
    if input and output then
      for i = 1,100,1 do
        local inp = input(i)
        if not inp then
          break
        end
        local out = output(i)
        if not out then
          break
        end
        table.insert(links, {output=out, input=inp})
      end
    end
  end
  return links
end

function _connect()
  local links = get_auto_connect_links()
  local link_manager = cutils.get_object_manager ("link")
  local linked_inputs = {}
  local linked_outputs = {}
  local checklinks = {}
  -- BUG: It seems like when we switch default sink,
  -- the link manager doesn't return all the old links for the sink monitor,
  -- so we make multiple connections to the same REAPER input... :-(
  for link_object in link_manager:iterate() do
    table.insert(checklinks, {o = link_object, ["link.input.port"] = link_object.properties["link.input.port"], ["link.input.node"] = link_object.properties["link.input.node"], ["link.output.port"] = link_object.properties["link.output.port"], ["link.output.node"] = link_object.properties["link.output.node"]})
  end
  for _, rememberlink in ipairs(checklinks) do
    local inport = rememberlink["link.input.port"]
    local outport = rememberlink["link.output.port"]
    if not linked_inputs[inport] then
      --print("Existing input", inport)
      linked_inputs[inport] = {}
    end
    table.insert(linked_inputs[inport], rememberlink)
    if not linked_outputs[outport] then
      --print("Existing output", outport)
      linked_outputs[outport] = {}
    end
    table.insert(linked_outputs[outport], rememberlink)
  end
  local new_links = {}
  for _, link in ipairs(links) do
    local skip = false
    if link.output.properties["port.physical"] or link.output.properties["port.monitor"] then
      --print("Check existing to input", link.input.properties["node.id"], link.input.properties["object.id"], link.input.properties["port.alias"])
      for _, ex in ipairs(linked_inputs[link.input.properties["object.id"]] or {}) do
        if ex["link.output.node"] == link.output.properties["node.id"] and ex["link.output.port"] == link.output.properties["object.id"] then
          --print("Found correct existing")
          skip = true
        else
          --print("Destroy an existing wrong link")
          ex.o:request_destroy()
        end
      end
    else
      --print("Check existing to output", link.output.properties["node.id"], link.output.properties["object.id"], link.output.properties["port.alias"])
      for _, ex in ipairs(linked_outputs[link.output.properties["object.id"]] or {}) do
        if ex["link.input.node"] == link.input.properties["node.id"] and ex["link.input.port"] == link.input.properties["object.id"] then
          --print("Found correct existing")
          skip = true
        else
          --print("Destroy an existing wrong link")
          ex.o:request_destroy()
        end
      end
    end
    if skip then
    else
      --print("Insert new link")
      table.insert(new_links, link)
    end
  end
  local rememberlinks = {}
  for _, link in ipairs(new_links) do
    local link_object = link_port(link.output, link.input)
    table.insert(rememberlinks, {o = link_object, ["link.input.port"] = link.input.properties["object.id"], ["link.input.node"] = link.input.properties["node.id"], ["link.output.port"] = link.output.properties["object.id"], ["link.output.node"] = link.output.properties["node.id"]})
  end
end

SimpleEventHook {
  name = "rav/default-change",
  interests = {
    EventInterest {
      Constraint { "event.type", "=", "metadata-changed" },
      Constraint { "metadata.name", "=", "default" },
      Constraint { "event.subject.key", "c", "default.audio.sink", "default.audio.source" },
    },
  },
  execute = function (event)
    print("auto-connect-ports: default-change event")
    _connect()
  end
}:register ()

function output_object_added(_, port)
  if not output_checks or output_checks[port.properties["port.alias"]] == 111 then
    print("auto-connect-ports: output_om object-added", port.properties["port.alias"])
    _connect()
  end
end

function input_object_added(_, port)
  if not input_checks or input_checks[port.properties["port.alias"]] == 111 then
    print("auto-connect-ports: input_om object-added", port.properties["port.alias"])
    _connect()
  end
end

function output_object_removed(_, port)
  if not output_checks or output_checks[port.properties["port.alias"]] == 222 then
    print("auto-connect-ports: output_om object-removed", port.properties["port.alias"])
    _connect()
  end
end

function input_object_removed(_, port)
  if not input_checks or input_checks[port.properties["port.alias"]] == 222 then
    print("auto-connect-ports: input_om object-removed", port.properties["port.alias"])
    _connect()
  end
end

output_om:connect("object-added", output_object_added)
input_om:connect("object-added", input_object_added)
output_om:connect("object-removed", output_object_removed)
input_om:connect("object-removed", input_object_removed)

all_nodes:activate()
output_om:activate()
input_om:activate()
